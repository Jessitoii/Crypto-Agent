import asyncio
from collections import deque, defaultdict
import time
import json
from telethon import TelegramClient, events
import websockets
from nicegui import ui, app # GUI Kütüphanesi
from exchange import PaperExchange
from brain import AgentBrain
from price_buffer import PriceBuffer
from utils import get_top_pairs
from binance_client import BinanceExecutionEngine # Dosya adın neyse
from data_collector import TrainingDataCollector

# AYARLAR
REAL_TRADING_ENABLED = True # <--- DİKKAT DÜĞMESİ! False yaparsan sadece simülasyon çalışır.

# Global Nesne
# ---------------------------------------------------------

# İzlenecek Telegram kanallarının/gruplarının ID'leri (veya kullanıcı adları)
TARGET_CHANNELS = ['cointelegraph', 'wublockchainenglish', 'CryptoRankNews', 'TheBlockNewsLite', 'whale_alert_io', 'coindesk', 'arkhamintelligence', 'glassnode',  ] 

# Binance
BINANCE_API_KEY = 'MKssy8laddEHXBwHgBke2unmW84GWDzyikBgtVAYWmYftMOKN24PJxN3yEmFNfvv'
BINANCE_API_SECRET = 'llhE2OX8feKiXqVXN9eQWF9RBoA4ChaFdxR6oMaWhjj5CdRZezZZW0ZEEGOzFZJC'
# İzlenecek pariteler (küçük harf)
# Binance
TARGET_PAIRS = get_top_pairs(50)  # Otomatik en çok işlem gören 50 pariteyi al
BASE_URL = "wss://stream.binance.com:9443/stream?streams="
STREAM_PARAMS = "/".join([f"{pair}@aggTrade" for pair in TARGET_PAIRS])
WEBSOCKET_URL = BASE_URL + STREAM_PARAMS
# MongoDB
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Crypto-Agent"
COLLECTION_NAME = "raw_events"

API_ID = 33059879
API_HASH = 'aac2748df0bff64aadcdc7692588b75b'
TELETHON_SESSION_NAME = 'crypto_agent_session'


# --- SİMÜLASYON AYARLARI ---
STARTING_BALANCE = 1000.0 # 1000 USDT ile başlıyoruz
LEVERAGE = 10             # 10x Kaldıraç (Acımasız olsun)
FIXED_TRADE_AMOUNT = 100  # Her işleme 100 USDT (Margin) basıyoruz (Total size = 1000 USDT)

class State:
    def __init__(self):
        self.is_running = True

class PriceBuffer:
    def __init__(self):
        self.buffer = deque()
        self.current_price = 0.0
    def add(self, p, t):
        self.current_price = p
        self.buffer.append((t, p))
        while self.buffer and self.buffer[0][0] < (t - 600): self.buffer.popleft()
    def get_change(self, sec=60):
        if not self.buffer: return 0.0
        target = self.buffer[-1][0] - sec
        old = next((p for t, p in self.buffer if t >= target), self.buffer[0][1])
        return ((self.current_price - old) / old) * 100

class PaperExchange:
    def __init__(self, balance):
        self.balance = balance
        self.positions = {} 
        self.total_pnl = 0.0

    def open_position(self, symbol, side, price, amount_usdt, leverage, tp_pct, sl_pct):
        if not app_state.is_running: return 

        if symbol in self.positions:
            log_ui(f"⚠️ {symbol} pozisyonu zaten açık.", "warning")
            return

        if self.balance < amount_usdt:
            log_ui("❌ Bakiye Yetersiz!", "error")
            return

        tp_price = price * (1 + tp_pct/100) if side == 'LONG' else price * (1 - tp_pct/100)
        sl_price = price * (1 - sl_pct/100) if side == 'LONG' else price * (1 + sl_pct/100)
        
        self.balance -= amount_usdt
        self.positions[symbol] = {
            'entry': price, 'qty': (amount_usdt * leverage) / price,
            'side': side, 'lev': leverage, 'margin': amount_usdt,
            'tp': tp_price, 'sl': sl_price, 'current_price': price,
            'pnl': 0.0
        }
        log_ui(f"🔵 POZİSYON AÇILDI: {symbol.upper()} {side} | Giriş: {price}", "info")
        # BURADAN refresh_ui() ÇAĞRISINI SİLDİK! UI KENDİNİ GÜNCELLEYECEK.

    def check_positions(self, symbol, current_price):
        if symbol not in self.positions: return
        pos = self.positions[symbol]
        pos['current_price'] = current_price
        
        if pos['side'] == 'LONG':
            pos['pnl'] = (current_price - pos['entry']) * pos['qty']
        else:
            pos['pnl'] = (pos['entry'] - current_price) * pos['qty']

        close_reason = None
        if pos['side'] == 'LONG':
            if current_price >= pos['tp']: close_reason = "TAKE PROFIT 💰"
            elif current_price <= pos['sl']: close_reason = "STOP LOSS 🛑"
        else:
            if current_price <= pos['tp']: close_reason = "TAKE PROFIT 💰"
            elif current_price >= pos['sl']: close_reason = "STOP LOSS 🛑"

        if close_reason:
            self.close_position(symbol, close_reason, pos['pnl'])

    def close_position(self, symbol, reason, pnl):
        pos = self.positions[symbol]
        self.balance += pos['margin'] + pnl
        self.total_pnl += pnl
        del self.positions[symbol]
        
        color = "success" if pnl > 0 else "error"
        log_ui(f"🏁 KAPANDI: {symbol.upper()} ({reason}) | PnL: {pnl:.2f} USDT", color)


# --- GLOBAL NESNELER ---
app_state = State()
market_memory = defaultdict(PriceBuffer)
exchange = PaperExchange(STARTING_BALANCE)
brain = AgentBrain(model='crypto-agent:gemma') 
real_exchange = BinanceExecutionEngine(BINANCE_API_KEY, BINANCE_API_SECRET)
collector = TrainingDataCollector()

# ---------------------------------------------------------
# UI FONKSİYONLARI (GÜVENLİ HALE GETİRİLDİ)
# ---------------------------------------------------------
def log_ui(message, type="info"):
    """Güvenli Loglama"""
    timestamp = time.strftime("%H:%M:%S")
    icon = "📝"
    if type == "success": icon = "✅"
    elif type == "error": icon = "❌"
    elif type == "warning": icon = "⚠️"
    
    full_msg = f"[{timestamp}] {icon} {message}"
    print(full_msg) 
    
    # Try-Except ile "Client deleted" hatasını engelliyoruz
    try:
        if log_container is not None:
            log_container.push(full_msg)
    except Exception:
        pass # UI ölü ise sadece konsola bas ve geç

# ---------------------------------------------------------
# ANA SAYFA TASARIMI
# ---------------------------------------------------------
@ui.page('/') 
def index():
    global log_container
    
    ui.colors(primary='#5898d4', secondary='#26a69a', accent='#9c27b0', dark='#1d1d1d')
    
    # HEADER
    with ui.header().classes(replace='row items-center') as header:
        ui.icon('smart_toy', size='32px')
        ui.label('CRYPTO AI AGENT DASHBOARD').classes('text-h6 font-bold')
        ui.space()
        with ui.row().classes("gap-4"):
            with ui.column():
                ui.label("CÜZDAN").classes("text-xs text-gray-300")
                balance_label = ui.label(f"${exchange.balance:.2f}").classes("text-xl font-mono font-bold")
            with ui.column():
                ui.label("TOPLAM K/Z").classes("text-xs text-gray-300")
                pnl_label = ui.label("$0.00").classes("text-xl font-mono font-bold text-green-500")
        
        def toggle_bot():
            app_state.is_running = not app_state.is_running
            status_badge.set_text("ÇALIŞIYOR" if app_state.is_running else "DURDURULDU")
            status_badge.classes(replace=f"text-white {'bg-green-600' if app_state.is_running else 'bg-red-600'} px-2 rounded")
            
        status_badge = ui.label("ÇALIŞIYOR").classes("bg-green-600 text-white px-2 rounded font-bold cursor-pointer")
        status_badge.on('click', toggle_bot)

    # CONTENT
    with ui.grid(columns=2).classes("w-full h-full gap-4 p-4"):
        with ui.column().classes("w-full"):
            ui.label("AÇIK POZİSYONLAR").classes("text-lg font-bold mb-2 text-blue-400")
            # Container'ı burada tanımlıyoruz ama global'e atamıyoruz
            positions_container = ui.column().classes("w-full gap-2")
            
        with ui.column().classes("w-full h-screen"):
            ui.label("CANLI LOG AKIŞI").classes("text-lg font-bold mb-2 text-yellow-400")
            log_container = ui.log(max_lines=100).classes("w-full h-96 bg-gray-900 text-green-400 font-mono text-sm p-2 border border-gray-700 rounded")

    # --- LOKAL REFRESH FONKSİYONU ---
    # Bu fonksiyon sadece bu tarayıcı sekmesi için çalışır.
    def refresh_local_ui():
        try:
            # Bakiyeleri güncelle
            balance_label.set_text(f"${exchange.balance:.2f}")
            pnl_label.set_text(f"${exchange.total_pnl:.2f}")
            pnl_label.style(f"color: {'green' if exchange.total_pnl >= 0 else 'red'}")
            
            # Pozisyonları yeniden çiz
            positions_container.clear()
            with positions_container:
                if not exchange.positions:
                    ui.label("Açık pozisyon yok...").classes("text-gray-500 italic")
                
                for sym, pos in exchange.positions.items():
                    pnl_color = "text-green-500" if pos['pnl'] >= 0 else "text-red-500"
                    with ui.card().classes("w-full p-2 bg-gray-800 border border-gray-700"):
                        with ui.row().classes("w-full justify-between"):
                            ui.label(f"{sym.upper()} {pos['side']} {pos['lev']}x").classes("font-bold text-lg")
                            ui.label(f"${pos['pnl']:.2f}").classes(f"font-bold text-xl {pnl_color}")
                        
                        with ui.row().classes("text-xs text-gray-400 gap-4"):
                            ui.label(f"Giriş: {pos['entry']}")
                            ui.label(f"Anlık: {pos['current_price']}")
                            ui.label(f"TP: {pos['tp']:.2f}")
                            ui.label(f"SL: {pos['sl']:.2f}")
        except Exception:
            pass # Eğer sayfa kapanırsa hata verme

    # Timer'ı sayfaya bağla (Global değil, local)
    ui.timer(1.0, refresh_local_ui)

# ---------------------------------------------------------
# ARKA PLAN GÖREVLERİ
# ---------------------------------------------------------
async def start_background_tasks():
    log_ui("Sistem Başlatılıyor...")
    
    # Gerçek borsa bağlantısı
    if REAL_TRADING_ENABLED:
        log_ui("⚠️ GERÇEK TİCARET MODU AKTİF! API'ye bağlanılıyor...", "warning")
        await real_exchange.connect()
    
    asyncio.create_task(websocket_loop())
    asyncio.create_task(telegram_loop())

async def websocket_loop():
    print(f"[SİSTEM] Websocket URL (Kısaltılmış): {WEBSOCKET_URL[:100]}...")
    while True:
        try:
            # 100 parite için timeout'u artırıyoruz
            async for ws in websockets.connect(WEBSOCKET_URL, ping_interval=None):
                log_ui("Websocket Bağlandı ✅", "success")
                try:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if 'data' in data:
                            payload = data['data']
                            pair = payload['s'].lower()
                            price = float(payload['p'])
                            ts = payload['T'] / 1000.0
                            
                            market_memory[pair].add(price, ts)
                            exchange.check_positions(pair, price)
                            
                        current_prices_dict = {p: market_memory[p].current_price for p in TARGET_PAIRS}
                        await collector.check_outcomes(current_prices_dict, log_ui)
                except Exception as e:
                    log_ui(f"WS Okuma Hatası: {e}", "error")
        except Exception as e:
            log_ui(f"WS Bağlantı Hatası (5sn Bekleniyor): {e}", "error")
            await asyncio.sleep(5)

async def telegram_loop():
    client = TelegramClient(TELETHON_SESSION_NAME, API_ID, API_HASH)
    await client.start()
    log_ui(f"Telegram {len(TARGET_CHANNELS)} Kanalı Dinliyor 📡", "success")
    
    @client.on(events.NewMessage(chats=TARGET_CHANNELS))
    async def handler(event):
        if not app_state.is_running: return
        msg = event.message.message
        if not msg: return
        
        for pair in TARGET_PAIRS:
            if pair.replace('usdt','') in msg.lower():
                log_ui(f"Haber: {pair.upper()}", "warning")
                
                stats = market_memory[pair]
                if stats.current_price == 0: continue

                # Analiz
                dec = await brain.analyze(msg, pair, stats.current_price, stats.get_change(60))
                
                # Data Collector
                collector.log_decision(msg, pair, stats.current_price, stats.get_change(60), dec, log_ui)

                if dec['confidence'] > 75 and dec['action'] in ['LONG', 'SHORT']:
                    validity = dec.get('validity_minutes', 15)
                    
                    # 1. Simülasyonu Güncelle (Ekranda görmek için)
                    exchange.open_position(
                        symbol=pair, 
                        side=dec['action'], 
                        price=stats.current_price, 
                        amount_usdt=FIXED_TRADE_AMOUNT, 
                        leverage=LEVERAGE, 
                        tp_pct=dec['tp_pct'], 
                        sl_pct=dec['sl_pct'],
                        validity_minutes=validity
                    )

                    # 2. GERÇEK İŞLEM (PARA BURADA GİDER)
                    if REAL_TRADING_ENABLED:
                        log_ui(f"🚀 API EMRİ GÖNDERİLİYOR: {pair.upper()}", "error") # Kırmızı uyarı
                        
                        # Bu işlemi arka plana atıyoruz ki Telegram döngüsünü kilitlemesin
                        asyncio.create_task(real_exchange.execute_trade(
                            symbol=pair,
                            side=dec['action'],
                            amount_usdt=FIXED_TRADE_AMOUNT, # Gerçek Para Miktarı
                            leverage=LEVERAGE,
                            tp_pct=dec['tp_pct'],
                            sl_pct=dec['sl_pct']
                        ))
                else:
                    log_ui(f"Karar: HOLD (Güven: %{dec['confidence']})", "warning")
                break
# UYGULAMAYI BAŞLAT
app.on_startup(start_background_tasks)
ui.run(title="Crypto AI Agent", dark=True, port=8080, reload=False)