import asyncio
import os
import pandas as pd
import sys
from binance import AsyncClient
from datetime import datetime, timedelta, timezone

# Kendi modüllerinden
from utils import get_top_100_map, check_is_stablecoin
COIN_MAP = get_top_100_map()
MANUAL_BINANCE_FUTURES_TICKERS = [
    # Ana Coinler
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "MATICUSDT",
    # Layer 1 & 2
    "NEARUSDT", "ATOMUSDT", "ALGOUSDT", "FTMUSDT", "APTUSDT", "SUIUSDT", "SEIUSDT", "OPUSDT", "ARBUSDT", "HBARUSDT",
    "INJUSDT", "LDOUSDT", "TIAUSDT", "STXUSDT", "EGLDUSDT", "FILUSDT", "ICPUSDT", "RUNEUSDT", "GRTUSDT", "AAVEUSDT",
    # Yapay Zeka (AI) & Render
    "FETUSDT", "RENDERUSDT", "TAOUSDT", "NEARUSDT", "AGIXUSDT", "WLDUSDT", "ARKMUSDT", "THETAUSDT",
    # Memecoinler (Özel Prefixli olanlar dahil)
    "DOGEUSDT", "1000PEPEUSDT", "1000SHIBUSDT", "1000BONKUSDT", "1000FLOKIUSDT", "WIFUSDT", "PEOPLEUSDT", "MEMEUSDT",
    "POPCATUSDT", "BOMEUSDT", "1000LUNCUSDT", "1000RATSUSDT",
    # DeFi & Diğer Popülerler
    "UNIUSDT", "SUSHIUSDT", "DYDXUSDT", "CRVUSDT", "MKRUSDT", "SNXUSDT", "PENDLEUSDT", "ENAUSDT", "ETHFIUSDT",
    "JUPUSDT", "PYTHUSDT", "STRKUSDT", "AXSUSDT", "IMXUSDT", "GALAUSDT", "BEAMXUSDT", "SANDUSDT", "MANAUSDT",
    # Eski Top Coinler
    "LTCUSDT", "BCHUSDT", "ETCUSDT", "XLMUSDT", "TRXUSDT", "VETUSDT", "NEOUSDT", "QTUMUSDT", "EOSUSDT", "IOTAUSDT",
    "ZECUSDT", "DASHUSDT", "XMRUSDT", "ONTUSDT", "ZILUSDT", "BATUSDT", "ENJUSDT", "KNCUSDT", "ANKRUSDT", "OCEANUSDT",
    "CHZUSDT", "ALICEUSDT", "FLOWUSDT", "KAVAUSDT", "GMXUSDT", "ORDIUSDT", "1000SATSUSDT", "GASUSDT", "TRBUSDT"
]
BASE_DIR = "data/market_cache"
KLINES_DIR = f"{BASE_DIR}/klines"
FUNDING_DIR = f"{BASE_DIR}/funding"

for d in [KLINES_DIR, FUNDING_DIR]:
    if not os.path.exists(d): os.makedirs(d)

async def download_symbol_data(client, symbol):
    """Bir coin için 1 yıllık kline ve funding verisini eksiksiz indirir."""
    try:
        # 1. MUM VERİLERİ (1m Klines)
        kline_path = f"{KLINES_DIR}/{symbol}_1m.pkl"
        if not os.path.exists(kline_path):
            klines = []
            # HATA BURADAYDI: Generator'ı await etmemiz gerekiyor
            gen = await client.futures_historical_klines_generator(symbol, "1m", "1 year ago UTC")
            async for k in gen:
                klines.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7])])
            
            if klines:
                df_k = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                df_k.to_pickle(kline_path)
        
        # 2. FUNDING RATE (Full Year Paging)
        """
        funding_path = f"{FUNDING_DIR}/{symbol}_funding.pkl"
        if not os.path.exists(funding_path):
            all_funding = []
            # Bir yıl önceki zaman damgası
            target_ts = int((datetime.now(timezone.utc) - timedelta(days=365)).timestamp() * 1000)
            end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            while True:
                # Geriye doğru (endTime kullanarak) 1000'erli çekiyoruz
                f_data = await client.futures_funding_rate(symbol=symbol, endTime=end_ts, limit=1000)
                if not f_data: break
                
                for f in f_data:
                    all_funding.append([int(f['fundingTime']), float(f['fundingRate'])])
                
                # En eski kaydın zamanını yeni 'end_ts' yapıyoruz (paging)
                new_end_ts = int(f_data[0]['fundingTime']) - 1
                if new_end_ts <= target_ts or new_end_ts == end_ts:
                    break
                end_ts = new_end_ts
                await asyncio.sleep(0.1) # Rate limit koruması

            if all_funding:
                df_f = pd.DataFrame(all_funding, columns=['ts', 'rate']).sort_values('ts')
                df_f.to_pickle(funding_path)
                """
        return True
    except Exception as e:
        print(f"\n💥 {symbol} Hatası: {e}")
        return False

async def main():
    client = await AsyncClient.create()
    symbols = MANUAL_BINANCE_FUTURES_TICKERS
    total_symbols = len(symbols)
    print(f"🚀 {total_symbols} coin için 1 yıllık veri madenciliği başladı...")
    for symbol in symbols:
        kline_path = f"{KLINES_DIR}/{symbol}_1m.pkl"
        if os.path.exists(kline_path):
            symbols.remove(symbol)
    total_symbols = len(symbols)
    print(f"🚀 {total_symbols} coin için 1 yıllık veri madenciliği başladı...")    

    batch_size = 3 # Ban riskine karşı hızı kontrollü tutuyoruz
    for i in range(0, total_symbols, batch_size):
        batch = symbols[i : i + batch_size]
        tasks = [download_symbol_data(client, s) for s in batch]
        await asyncio.gather(*tasks)
        
        # İlerleme Göstergesi
        progress = min(i + batch_size, total_symbols)
        percent = (progress / total_symbols) * 100
        sys.stdout.write(f"\r📦 İlerleme: %{percent:.2f} [{progress}/{total_symbols}]")
        sys.stdout.flush()
        
        await asyncio.sleep(0.5)

    await client.close_connection()
    print("\n🏁 Operasyon başarıyla tamamlandı. Veriler RAM'e yüklenmeye hazır!")

if __name__ == "__main__":
    asyncio.run(main())