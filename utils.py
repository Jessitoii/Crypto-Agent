import requests

def get_top_pairs(limit=50):
    """Binance'den son 24 saatte en çok hacim yapan USDT paritelerini çeker"""
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = requests.get(url).json()
        
        # Sadece USDT paritelerini filtrele (UP/DOWN ve Stablecoinler hariç)
        filtered = [
            x for x in response 
            if x['symbol'].endswith('USDT') 
            and 'UPUSDT' not in x['symbol'] 
            and 'DOWNUSDT' not in x['symbol']
            and x['symbol'] not in ['USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT']
        ]
        
        # Hacme (quoteVolume) göre sırala ve ilk X tanesini al
        sorted_pairs = sorted(filtered, key=lambda x: float(x['quoteVolume']), reverse=True)[:limit]
        
        # Bizim formatımıza çevir (küçük harf)
        return [x['symbol'].lower() for x in sorted_pairs]
    except Exception as e:
        print(f"HATA: Parite listesi çekilemedi! {e}")
        # Hata olursa default listeye dön
        return ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt']

# KULLANIMI:
# TARGET_PAIRS = get_top_pairs(100)  <-- Bunu yaparsan otomatik olur.