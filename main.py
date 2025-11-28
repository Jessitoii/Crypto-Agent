import asyncio
from collections import defaultdict
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
from dotenv import load_dotenv
import os 
import datetime
import re 
# AYARLAR
REAL_TRADING_ENABLED = True # <--- DİKKAT DÜĞMESİ! False yaparsan sadece simülasyon çalışır.

# İzlenecek Telegram kanallarının/gruplarının ID'leri (veya kullanıcı adları)
TARGET_CHANNELS = ['cointelegraph', 'wublockchainenglish', 'CryptoRankNews', 'TheBlockNewsLite', 'whale_alert_io', 'coindesk', 'arkhamintelligence', 'glassnode',  ] 
name_map = {
        'polygon': 'matic',
        'ripple': 'xrp',
        'cardano': 'ada',
        'avalanche': 'avax',
        'dogecoin': 'doge',
        'ethereum': 'eth',
        'bitcoin': 'btc',
        'bnb chain': 'bnb',
        'solana': 'sol',
        'arbitrum': 'arb',
        'optimism': 'op'
    }

# İzlenecek pariteler (küçük harf)
TARGET_PAIRS = get_top_pairs(50)  # Otomatik en çok işlem gören 50 pariteyi al
# --- Environments --- 
load_dotenv()
BASE_URL = os.getenv('BASE_URL')
STREAM_PARAMS = "/".join([f"{pair}@aggTrade" for pair in TARGET_PAIRS])
WEBSOCKET_URL = BASE_URL + STREAM_PARAMS
# Telethon
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
TELETHON_SESSION_NAME = os.getenv('TELETHON_SESSION_NAME')
MODEL = os.getenv('MODEL')
# Binance
# BU ŞALTERE DİKKAT ET!
# True  = MAINNET (Gerçek Para Gider)
# False = TESTNET (Binance Kum Havuzu)
USE_MAINNET = False 

if USE_MAINNET:
    API_KEY = os.getenv('BINANCE_API_KEY')
    API_SECRET = os.getenv('BINANCE_API_SECRET')
    IS_TESTNET = False
    print("\n" + "#"*40)
    print("🚨 DİKKAT: MAINNET MODU AKTİF!")
    print("🚨 GERÇEK PARA RİSK ALTINDA!")
    print("#"*40 + "\n")
else:
    API_KEY = os.getenv('BINANCE_API_KEY_TESTNET')
    API_SECRET = os.getenv('BINANCE_API_SECRET_TESTNET')
    IS_TESTNET = True
    print("\n" + "-"*40)
    print("🧪 TESTNET MODU AKTİF")
    print("🧪 İşlemler Binance Test Sunucularında Yapılacak")
    print("-"*40 + "\n")

# --- SİMÜLASYON AYARLARI ---
STARTING_BALANCE = 1000.0 # 1000 USDT ile başlıyoruz
LEVERAGE = 10             # 10x Kaldıraç (Acımasız olsun)
FIXED_TRADE_AMOUNT = 100  # Her işleme 100 USDT (Margin) basıyoruz (Total size = 1000 USDT)

class State:
    def __init__(self):
        self.is_running = True

# --- GLOBAL NESNELER ---
app_state = State()
market_memory = defaultdict(PriceBuffer)
exchange = PaperExchange(STARTING_BALANCE)
brain = AgentBrain() 
real_exchange = BinanceExecutionEngine(API_KEY, API_SECRET, testnet=IS_TESTNET)
collector = TrainingDataCollector()

# ---------------------------------------------------------
# UI FONKSİYONLARI (GÜVENLİ HALE GETİRİLDİ)
# ---------------------------------------------------------
def log_txt(message, filename):
    message = f"\n######################\nTime : {datetime.datetime.now()}\n" + message
    message += "\n######################\n"
    open(file=filename, mode='a', encoding='utf-8').write(message)

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
    
    # --- HEADER ---
    with ui.header().classes(replace='row items-center') as header:
        ui.icon('smart_toy', size='32px')
        ui.label('CRYPTO AI AGENT DASHBOARD').classes('text-h6 font-bold')
        ui.space()
        
        # Cüzdan Bilgileri
        with ui.row().classes("gap-4"):
            with ui.column():
                ui.label("CÜZDAN").classes("text-xs text-gray-300")
                balance_label = ui.label(f"${exchange.balance:.2f}").classes("text-xl font-mono font-bold")
            with ui.column():
                ui.label("TOPLAM K/Z").classes("text-xs text-gray-300")
                pnl_label = ui.label("$0.00").classes("text-xl font-mono font-bold text-green-500")
        
        # Durdurma Butonu
        def toggle_bot():
            app_state.is_running = not app_state.is_running
            status_badge.set_text("ÇALIŞIYOR" if app_state.is_running else "DURDURULDU")
            status_badge.classes(replace=f"text-white {'bg-green-600' if app_state.is_running else 'bg-red-600'} px-2 rounded")
            
        status_badge = ui.label("ÇALIŞIYOR").classes("bg-green-600 text-white px-2 rounded font-bold cursor-pointer")
        status_badge.on('click', toggle_bot)

    # --- MANUEL HABER GİRİŞ ALANI (YENİ) ---
    with ui.row().classes('w-full p-4 bg-gray-900 border-b border-gray-700 items-center gap-2'):
        ui.icon('edit_note', size='24px').classes('text-blue-400')
        news_input = ui.input(placeholder="Manuel Haber Simülasyonu: 'Bitcoin ETF approved by SEC...'").classes('w-3/5 text-white').props('dark')
        
        async def manual_submit():
            text = news_input.value
            if text:
                news_input.value = "" # Kutuyu temizle
                # Ortak fonksiyonu çağırıyoruz
                await process_news(text, source="MANUAL")
        
        ui.button('ANALİZ ET & İŞLEME SOK', on_click=manual_submit).classes('bg-blue-600 text-white')

    # --- CONTENT GRID ---
    with ui.grid(columns=2).classes("w-full h-full gap-4 p-4"):
        with ui.column().classes("w-full"):
            ui.label("AÇIK POZİSYONLAR").classes("text-lg font-bold mb-2 text-blue-400")
            positions_container = ui.column().classes("w-full gap-2")
            
        with ui.column().classes("w-full h-screen"):
            ui.label("CANLI LOG AKIŞI").classes("text-lg font-bold mb-2 text-yellow-400")
            log_container = ui.log(max_lines=100).classes("w-full h-96 bg-gray-900 text-green-400 font-mono text-sm p-2 border border-gray-700 rounded")

    # --- LOKAL REFRESH ---
    def refresh_local_ui():
        # (Burası aynı kalacak, önceki kodundaki refresh_local_ui içeriği)
        try:
            balance_label.set_text(f"${exchange.balance:.2f}")
            pnl_label.set_text(f"${exchange.total_pnl:.2f}")
            pnl_label.style(f"color: {'green' if exchange.total_pnl >= 0 else 'red'}")
            
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
        except Exception: pass

    ui.timer(1.0, refresh_local_ui)
    
# ---------------------------------------------------------
# ARKA PLAN GÖREVLERİ
# ---------------------------------------------------------
async def start_background_tasks():
    log_ui("Sistem Başlatılıyor...")
    
    # ARTIK HER DURUMDA BAĞLANIYORUZ
    # Çünkü Testnet de olsa Mainnet de olsa bir API bağlantısı şart.
    target_env = "MAINNET 🚨" if USE_MAINNET else "TESTNET 🧪"
    log_ui(f"Borsa Bağlantısı Başlatılıyor ({target_env})...", "warning")
    
    await real_exchange.connect()
    
    asyncio.create_task(websocket_loop())
    asyncio.create_task(telegram_loop())
    asyncio.create_task(collector_loop())

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
                            log, color = exchange.check_positions(pair, price)
                            if log or color : log_ui(log, color)
                except Exception as e:
                    log_ui(f"WS Okuma Hatası: {e}", "error")
        except Exception as e:
            log_ui(f"WS Bağlantı Hatası (5sn Bekleniyor): {e}", "error")
            await asyncio.sleep(5)

async def process_news(msg, source="TELEGRAM"):
    if not app_state.is_running: return

    log_ui(f"[{source}] Analiz Ediliyor: {msg[:50]}...", "info")
    
    # 1. BEYİN ANALİZİ (Tüm market listesini gönderiyoruz)
    # LLM'e sadece 'BTC', 'ETH' gibi saf isimleri yolluyoruz, USDT kalabalığı yapmasın.
    response = await brain.analyze(msg, TARGET_PAIRS)
    
    trades = response.get('trades', [])
    
    if not trades:
        log_ui(f"[{source}] İlgili parite bulunamadı veya pas geçildi.", "info")
        print(response)
        return

    # 2. LLM'DEN GELEN EMİRLERİ İŞLE
    for trade in trades:
        symbol_raw = trade.get('symbol', '').lower()
        action = trade.get('action', 'HOLD')
        confidence = trade.get('confidence', 0)
        
        # LLM bazen 'BTC' döner, bazen 'Bitcoin'. Bizim listemizle eşleştirelim.
        # Basitçe sonuna 'usdt' ekleyip listemizde var mı bakalım.
        pair = f"{symbol_raw}usdt"
        
        # Listemizde yoksa (Örn: LLM 'XMR' dedi ama biz izlemiyoruz) geç.
        if pair not in TARGET_PAIRS:
            log_ui(f"⚠️ LLM '{symbol_raw}' önerdi ama izleme listesinde yok.", "warning")
            continue
            
        # Market verisini çek
        stats = market_memory[pair]
        if stats.current_price == 0:
            log_ui(f"⚠️ {pair.upper()} fiyat verisi eksik.", "error")
            continue

        log_ui(f"🎯 HEDEF TESPİT EDİLDİ: {pair.upper()} -> {action}", "success")

        # Güven Kontrolü
        if confidence > 75 and action in ['LONG', 'SHORT']:
            validity = trade.get('validity_minutes', 15)
            tp_pct = trade.get('tp_pct', 2.0)
            sl_pct = trade.get('sl_pct', 1.0)

            # A. Paper Trading
            log, color = exchange.open_position(
                symbol=pair,
                side=action,
                price=stats.current_price,
                amount_usdt=FIXED_TRADE_AMOUNT,
                leverage=LEVERAGE,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                validity=validity,
                app_state=app_state
            )
            
            full_log = log + f'\nSrc: {source}\nReason: {trade.get("reason")}'
            log_ui(full_log, color)
            log_txt(full_log, "trade_logs.txt")
            
            # Veri Toplayıcı (Collector)
            # Not: Collector yapısını çoklu işlem için güncellemek gerekebilir ama şimdilik loglayalım
            collector.log_decision(msg, pair, stats.current_price, stats.get_change(60), trade)

            # B. Real Trading
            if REAL_TRADING_ENABLED:
                env_label = "MAINNET" if USE_MAINNET else "TESTNET"
                log_ui(f"🚀 {env_label} API: {pair.upper()} {action}", "error")
                
                asyncio.create_task(real_exchange.execute_trade(
                    symbol=pair,
                    side=action,
                    amount_usdt=FIXED_TRADE_AMOUNT,
                    leverage=LEVERAGE,
                    tp_pct=tp_pct,
                    sl_pct=sl_pct
                ))
        else:
            log_ui(f"Pas Geçildi: {pair.upper()} {action} (Güven: %{confidence})", "warning")

async def telegram_loop():
    client = TelegramClient(TELETHON_SESSION_NAME, API_ID, API_HASH)
    await client.start()
    log_ui(f"Telegram {len(TARGET_CHANNELS)} Kanalı Dinliyor 📡", "success")
    
    @client.on(events.NewMessage(chats=TARGET_CHANNELS))
    async def handler(event):
        msg = event.message.message
        if msg:
            # Tüm mantığı process_news'e devrettik
            await process_news(msg, source="TELEGRAM")

async def collector_loop():
    """Eğitim verilerini kontrol eden düşük öncelikli döngü"""
    log_ui("Data Collector Başlatıldı 💾", "success")
    while True:
        try:
            await asyncio.sleep(60) # Her 60 saniyede bir kontrol et (PC'yi yormaz)
            
            if not market_memory: continue
            
            # Anlık fiyatları çek
            current_prices_dict = {p: market_memory[p].current_price for p in TARGET_PAIRS if market_memory[p].current_price > 0}
            
            if current_prices_dict:
                await collector.check_outcomes(current_prices_dict)
                
        except Exception as e:
            print(f"Collector Hatası: {e}")

# UYGULAMAYI BAŞLAT
app.on_startup(start_background_tasks)
ui.run(title="Crypto AI Agent", dark=True, port=8080, reload=False)