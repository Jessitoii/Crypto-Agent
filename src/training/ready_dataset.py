import json
import re

def clean_news_text(text):
    # 1. URL'leri temizle (http, https)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\S+', '', text)
    # 2. Telegram/Twitter handle'larını temizle (@cointelegraph vb.)
    text = re.sub(r'@\w+', '', text)
    # 3. Markdown link kalıntılarını ve buton metinlerini temizle
    text = re.sub(r'\[News\]\(.*?\)|\[Markets\]\(.*?\)|\[YouTube\]\(.*?\)', '', text, flags=re.IGNORECASE)
    # 4. Kalınlaştırma (**) işaretlerini kaldır
    text = text.replace('**', '')
    # 5. Gereksiz boşlukları ve satır başlarını temizle
    text = text.replace('**', '').replace('🚨 NOW:', '').replace('🚨 BREAKING:', '')
    text = text.replace("[— link]( ", "")
    # Gereksiz boşlukları al
    return " ".join(text.split()).strip()

def refine_nexus_data_v2(input_file):
    raw_data = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            raw_data.append(json.loads(line))
    
    refined_dataset = []
    shorts = 0
    longs = 0

    for item in raw_data:
        # 1. Gelişmiş News Ayıklama (Regex yerine Split bazlı daha güvenli yöntem)
        try:
            #input_str = item['input']
            news_part = item['news'].strip()
            
            # 2. Metrik Ayıklama
            
            mcap = item["data"]["market_cap"]
            rsi = float(item["data"]["rsi"])
            funding = float(item["data"]["funding"])
            # Momentum (1 saatlik) verisini çekiyoruz
            momentum = float(item["data"]["momentum"]["1h"])
            
            clean_symbol = item["data"]["symbol"].replace("USDT", "")
            #gemma_output = item['output']
            action = item['data']['action']
            #reasoning = item['output']['reason']
            tp_pct = item['data']['peak_pct']
            validity_minutes = item['data']['peak_min']


            if not (action == "LONG" or action == "SHORT"):
                continue
            
            if action == "LONG":
                longs+=1
            else: 
                shorts +=1
            # 4. Sayısal Veriyi "Semantic Token"lara Dönüştürme (NLP Kolu İçin)
            """
            mcap_label = "LARGE" if mcap > 10 else "MID" if mcap > 1 else "SMALL"
            rsi_label = "OVERBOUGHT" if rsi > 70 else "OVERSOLD" if rsi < 30 else "NEUTRAL"
            mom_label = "BULLISH_MOM" if momentum > 0.5 else "BEARISH_MOM" if momentum < -0.5 else "FLAT"
            """
            # DeBERTa'nın bağlamı anlaması için düzleştirilmiş metin
            news_part = clean_news_text(news_part) 
            synthetic_input = f"[N] {news_part} [C] {clean_symbol}"
            refined_dataset.append({
                "text": synthetic_input,
                "label": {"HOLD": 0, "SHORT": 1, "LONG": 2}[action],
                "quant_features": { # MLP koluna gidecek ham veriler
                    "mcap": mcap,
                    "rsi": rsi,
                    "funding": funding,
                    "momentum": momentum
                },
                #"reasoning": reasoning, # SetFit Reasoning-Aware için
                "tp_pct": tp_pct,
                "validity_minutes": validity_minutes
            })

        except Exception as e:
            print(f"Satır atlandı, hata: {e}")

    print(f"Long : {longs} | Shorts : {shorts}")
    return refined_dataset

def elite_purge(dataset):
    clean_data = []
    purged_count = 0
    
    for row in dataset:
        q = row['quant_features']
        label = row['label']
        
        # ELEME MANTIĞI: Başarılı ama 'Kirli' Sinyaller
        is_dirty = False
        
        if label == 2: # LONG (Fiyat gerçekten gitmiş ama...)
            if q['rsi'] > 70 or q['funding'] > 0.08 or q['momentum'] > 2.2:
                is_dirty = True # Çok şişmiş piyasada gelen 'tesadüfi' başarı
        
        elif label == 1: # SHORT (Fiyat gerçekten düşmüş ama...)
            if q['rsi'] < 30 or q['funding'] < -0.05 or q['momentum'] < -2.2:
                is_dirty = True # Zaten çakılmış piyasada gelen 'tesadüfi' başarı
                
        if not is_dirty:
            clean_data.append(row)
        else:
            purged_count += 1
            
    print(f"İmha edilen kirli veri sayısı: {purged_count}")
    print(f"Kalan elit veri seti: {len(clean_data)}")
    return clean_data

refined_dataset = refine_nexus_data_v2('data/nexus_elite_v2_12_2.jsonl')

with open('data/nexus_elite_v2_12.json', 'w', encoding='utf-8') as f:
    json.dump(refined_dataset, f, ensure_ascii=False, indent=2)