import asyncio
from asyncio import Queue
import motor.motor_asyncio  # Bu, 'pymongo' değil! Bu 'Motor'.
from telethon import TelegramClient, events
from binance import AsyncClient, BinanceSocketManager # Async desteği kritik

# --- 1. Yapılandırma (TÜMÜNÜ DOLDUR) ---
# Telethon
API_ID = 33059879
API_HASH = 'aac2748df0bff64aadcdc7692588b75b'
TELETHON_SESSION_NAME = 'trading_bot_session'
# İzlenecek Telegram kanallarının/gruplarının ID'leri (veya kullanıcı adları)
TARGET_CHANNELS = ['CryptoNewsChannel', 'SomeWhaleAlert'] 

# Binance
BINANCE_API_KEY = 'YOUR_BINANCE_KEY'
BINANCE_API_SECRET = 'YOUR_BINANCE_SECRET'
# İzlenecek pariteler (küçük harf)
TARGET_PAIRS = ['btcusdt', 'ethusdt']

# MongoDB
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "trading_data"
COLLECTION_NAME = "raw_events"


# --- 2. Üretici 1: Telegram ---
async def telegram_producer(queue: Queue):
    print("Telegram Üreticisi Başlatılıyor...")
    client = TelegramClient(TELETHON_SESSION_NAME, API_ID, API_HASH)
    
    @client.on(events.NewMessage(chats=TARGET_CHANNELS))
    async def handler(event):
        # Bu handler'daki işlem 'await' içermeli ve HIZLI olmalı
        data = {
            'source': 'telegram',
            'channel': event.chat.username if event.chat else 'unknown',
            'message': event.message.message,
            'timestamp': event.message.date.timestamp()
        }
        await queue.put(data)
        print(f"[TELEGRAM] Kuyruğa eklendi: {event.message.message[:20]}...")

    await client.start() # Oturum açman gerekecek (ilk çalıştırmada)
    print("Telegram Üreticisi BAŞLADI.")
    await client.run_until_disconnected()


# --- 3. Üretici 2: Borsa Websocket ---
async def websocket_producer(queue: Queue):
    print("Websocket Üreticisi Başlatılıyor...")
    client = await AsyncClient.create(BINANCE_API_KEY, BINANCE_API_SECRET)
    bm = BinanceSocketManager(client)
    
    # Her parite için bir 'trade' akışı başlat
    streams = [f"{pair}@trade" for pair in TARGET_PAIRS]

    async with bm.multiplex_socket(streams) as socket:
        while True:
            # Bu, 'await' ile bekler ve tıkanmaz (non-blocking)
            msg = await socket.recv()
            
            # Hata mesajlarını filtrele
            if msg.get('e') == 'error':
                print(f"[WEBSOCKET] Hata: {msg['m']}")
                continue

            data = {
                'source': 'websocket',
                'pair': msg['s'],
                'price': msg['p'],
                'volume': msg['q'],
                'timestamp': msg['T'] / 1000.0 # Milisaniyeden saniyeye çevir
            }
            await queue.put(data)
            # print(f"[WEBSOCKET] Kuyruğa eklendi: {data['pair']} @ {data['price']}")

    await client.close_connection()


# --- 4. Tüketici: Veritabanı Yazıcısı ---
async def consumer(queue: Queue, db):
    print("Tüketici Başlatılıyor...")
    collection = db[COLLECTION_NAME]
    while True:
        # Kuyruktan bir öğeyi 'await' ile bekle (tıkanmaz)
        data = await queue.get()
        
        try:
            # Veritabanına 'await' ile yaz (tıkanmaz)
            await collection.insert_one(data)
            # print(f"[DB] Kaydedildi: {data['source']}")
        except Exception as e:
            print(f"[DB] YAZMA HATASI: {e}")
            # Burada hatayı nasıl yöneteceğine karar vermelisin
            # Şimdilik görmezden geliyoruz, ancak bu KÖTÜ bir pratik
            pass
        
        # Kuyruğa bu görevin bittiğini bildir
        queue.task_done()


# --- 5. Ana Orkestratör ---
async def main():
    print("Sistem Başlatılıyor...")
    
    # Kuyruk ve DB Bağlantısını kur
    queue = Queue(maxsize=10000) # Geri Basınç (Backpressure) için bir limit koy
    
    mongo_client = motor.motor_asyncio.AsyncMotorClient(MONGO_URI)
    db = mongo_client[DB_NAME]
    
    print("Görevler oluşturuluyor...")
    
    # 3 ana görevi oluştur
    producer_tele_task = asyncio.create_task(telegram_producer(queue))
    producer_ws_task = asyncio.create_task(websocket_producer(queue))
    consumer_task = asyncio.create_task(consumer(queue, db))
    
    # Tüm görevleri 'aynı anda' çalıştır ve biri çökene kadar bekle
    await asyncio.gather(
        producer_tele_task,
        producer_ws_task,
        consumer_task
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSistem manuel olarak durduruldu.")