import json
import requests
import sys
from groq import AsyncGroq
import asyncio
from config import GROQCLOUD_API_KEY
# OLLAMA CONFIG
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama-3.3-70b-versatile"

def _extract_response(text):
        """
        Modelin gevezeliğini temizler, sadece JSON bloğunu alır.
        """
        if not text:
            return ""
        
        try:
            # 1. Markdown kod bloklarını (```json ... ```) temizle
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            # 2. En dıştaki { ve } parantezlerini bul (Metin arasındaki JSON'ı cımbızla çeker)
            start = text.find('{')
            end = text.rfind('}')
            
            if start != -1 and end != -1:
                return text[start:end+1]
            
            return text.strip()
        except Exception:
            return text.strip()

async def ask_teacher_llm(news, symbol, rsi, btc_trend, momentum, action, peak_pct, funding, market_cap, category, peak_min):
    """
    Güçlü bir yerel modele (Teacher) veriyi analiz ettirir.
    """
    prompt = f"""
    You are a Senior Crypto Quantitative Trader. 
    Analyze the following event and provide a 2-3 sentence 'Reasoning' for the outcome.
    
    NEWS: {news}
    SYMBOL: {symbol}
    MARKET DATA: RSI is {rsi}, BTC Trend is {btc_trend}%, 1h Momentum is {momentum}%, funding rate is {funding}%, market cap is {market_cap}, category is {category}
    ACTUAL OUTCOME: The price moved {peak_pct}% in {peak_min} minutes causing a {action} action.
    
    Your task: Explain the logical linkage between the news, the technicals, and the outcome. 
    If the news is bad but price went up, explain it as a 'Short Squeeze' or 'Sell the news' exhaustion.
    Keep the reasoning professional, objective, and in English. Vary your tone and structure. Sometimes start with the market context, sometimes with the news sentiment. Act like a raw trader writing in a high-stakes journal.
    
    Reasoning:"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    client = AsyncGroq(api_key=GROQCLOUD_API_KEY)
    try:
        response = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}])
        final_res = _extract_response(response.choices[0].message.content.strip())
        return final_res
    except Exception as e:
        print(f"Error: {e}")
        return None

async def process_distillation(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    final_dataset = []
    total = len(lines)
    
    print(f"🧠 {total} satır için 'Teacher-Student' damıtma işlemi başladı...")

    for i, line in enumerate(lines):
        row = json.loads(line)
        news = row['news']
        d = row['data']
        
        # Öğretmen modele soruyoruz (Anomali falan silmiyoruz, hepsini açıklatıyoruz!)
        reasoning = await ask_teacher_llm(
            news, d['symbol'], d['rsi'], d['btc_trend'], 
            d['momentum']['1h'], d['action'], d['peak_pct'], d['funding'], d['market_cap'], d['category'], d['peak_min']
        )
        
        if reasoning:
            entry = {
                "instruction": "Analyze the crypto news and metrics to provide a directional trading decision with professional reasoning.",
                "input": f"News: {news}\nSymbol: {d['symbol']}\nRSI: {d['rsi']}\nBTC: {d['btc_trend']}%\nFunding: {d['funding']}%\nMarket Cap: {d['market_cap']}\nCategory: {d['category']}\nMomentum: 1h: {d['momentum']['1h']}%",
                "output": f"Analysis: {reasoning}\nAction: {d['action']}\nPeak: {d['peak_pct']}% in {d['peak_min']} minutes"
            }
            final_dataset.append(entry)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_dataset, f, indent=4)        
        # İlerleme Logu
        sys.stdout.write(f"\r📦 İşlenen: {i+1}/{total} | Başarı: {len(final_dataset)}")
        sys.stdout.flush()

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, indent=4)

if __name__ == "__main__":
    asyncio.run(process_distillation("data/raw_market_outcomes_v1_5.jsonl", "data/synthetic_finetune_data.json"))