import asyncio
import json
import ollama # pip install ollama

class AgentBrain:
    # Modeli 'crypto-agent' olarak değiştiriyoruz (Oluşturduğumuz özel model)
    def __init__(self, model='crypto-agent'): 
        self.model = model
        print(f"[BEYİN] Özel Model Yüklendi: {self.model}")

    async def analyze(self, news, pair, price, chg):
        # Artık sadece veriyi veriyoruz, rol yapmayı öğrettik zaten.
        prompt = f"""
        DATA INPUT:
        News: "{news}"
        Pair: {pair}
        Current Price: {price}
        1m Change: {chg}%
        """
        try:
            res = await asyncio.to_thread(
                ollama.chat, 
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                format='json', # JSON zorlaması
                options={'temperature': 0.1}
            )
            return json.loads(res['message']['content'])
        except Exception as e:
            print(f"[HATA] LLM Analizi: {e}")
            return {"action": "HOLD", "confidence": 0}