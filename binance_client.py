from binance import AsyncClient
from binance.enums import *
from binance.enums import FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, FUTURE_ORDER_TYPE_STOP_MARKET

class BinanceExecutionEngine:
    def __init__(self, api_key, api_secret, testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.testnet = testnet
        # Her parite için 'stepSize' (Miktar hassasiyeti) ve 'tickSize' (Fiyat hassasiyeti) tutacağız
        self.symbol_info = {} 

    async def connect(self):
        """API'ye bağlanır ve parite kurallarını çeker"""
        try:
            self.client = await AsyncClient.create(self.api_key, self.api_secret, testnet=self.testnet)
            # Exchange Info'yu çekip filtreleri önbelleğe alıyoruz (Çok kritik!)
            info = await self.client.futures_exchange_info()
            
            for symbol_data in info['symbols']:
                symbol = symbol_data['symbol'].lower()
                filters = {f['filterType']: f for f in symbol_data['filters']}
                self.symbol_info[symbol] = {
                    'stepSize': float(filters['LOT_SIZE']['stepSize']),
                    'tickSize': float(filters['PRICE_FILTER']['tickSize']),
                    'minQty': float(filters['LOT_SIZE']['minQty'])
                }
            print(f"✅ [GERÇEK BORSA] Bağlantı başarılı. {len(self.symbol_info)} parite kuralı yüklendi.")
        except Exception as e:
            print(f"❌ [GERÇEK BORSA HATASI] Bağlanamadı: {e}")

    def _round_step(self, quantity, step_size):
        """Miktarı borsanın kabul edeceği hassasiyete yuvarlar"""
        return float(int(quantity / step_size) * step_size)

    def _round_price(self, price, tick_size):
        """Fiyatı borsanın kabul edeceği hassasiyete yuvarlar"""
        return float(round(price / tick_size) * tick_size)

    async def execute_trade(self, symbol, side, amount_usdt, leverage, tp_pct, sl_pct):
        """
        1. Kaldıracı ayarlar.
        2. Miktarı hesaplar.
        3. Market emri girer.
        4. (Opsiyonel) TP/SL emirlerini yerleştirir.
        """
        symbol = symbol.upper()
        symbol_lower = symbol.lower()
        
        if not self.client:
            print("⚠️ API Bağlı değil!")
            return

        try:
            # 1. Kaldıraç Ayarla
            await self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # 2. Anlık Fiyatı Al (Miktar hesaplamak için)
            ticker = await self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])

            # 3. Miktarı Hesapla (USDT -> Coin Adedi)
            # Formül: (Para * Kaldıraç) / Fiyat
            raw_qty = (amount_usdt * leverage) / current_price
            
            # Hassasiyet Ayarı (Burası hayat kurtarır)
            step_size = self.symbol_info[symbol_lower]['stepSize']
            qty = self._round_step(raw_qty, step_size)
            
            if qty < self.symbol_info[symbol_lower]['minQty']:
                print(f"⚠️ [HATA] Miktar çok düşük: {qty} (Min: {self.symbol_info[symbol_lower]['minQty']})")
                return

            print(f"🚀 [GERÇEK İŞLEM] {symbol} {side} | Lev: {leverage}x | Qty: {qty}")

            # 4. Ana Market Emri (Giriş)
            # Binance'de BUY=LONG, SELL=SHORT
            order_side = SIDE_BUY if side == 'LONG' else SIDE_SELL
            
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=qty
            )
            
            entry_price = float(order['avgPrice']) if 'avgPrice' in order else current_price
            print(f"✅ GİRİŞ BAŞARILI: Ort. Fiyat {entry_price}")

            # 5. Stop Loss ve Take Profit Emirleri (Bracket Orders)
            # Giriş başarılıysa hemen koruma emirlerini diziyoruz
            await self._place_tp_sl(symbol, side, qty, entry_price, tp_pct, sl_pct)
            
            return order

        except Exception as e:
            print(f"❌ [KRİTİK İŞLEM HATASI] {e}")
            # Hata durumunda (varsa) açık pozisyonu kapatmaya çalışmak gerekebilir (Advanced)

    async def _place_tp_sl(self, symbol, side, qty, entry_price, tp_pct, sl_pct):
        """TP ve SL emirlerini 'Reduce Only' olarak girer"""
        try:
            tick_size = self.symbol_info[symbol.lower()]['tickSize']
            
            # Fiyatları Hesapla
            if side == 'LONG':
                tp_price = self._round_price(entry_price * (1 + tp_pct/100), tick_size)
                sl_price = self._round_price(entry_price * (1 - sl_pct/100), tick_size)
                close_side = SIDE_SELL
            else: # SHORT
                tp_price = self._round_price(entry_price * (1 - tp_pct/100), tick_size)
                sl_price = self._round_price(entry_price * (1 + sl_pct/100), tick_size)
                close_side = SIDE_BUY

            # STOP LOSS Emri (Piyasa Stopu)
            await self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                stopPrice=sl_price,
                closePosition=True # Tüm pozisyonu kapat
            )
            print(f"🛡️ SL Kuruldu: {sl_price}")

            # TAKE PROFIT Emri (Limit veya Market)
            await self.client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                stopPrice=tp_price,
                closePosition=True
            )
            print(f"💰 TP Kuruldu: {tp_price}")

        except Exception as e:
            print(f"⚠️ [TP/SL HATASI] Koruma emirleri girilemedi! Manuel kapat: {e}")

    async def close(self):
        await self.client.close_connection()