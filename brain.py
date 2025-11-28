from google import genai
import json
import ollama 
import os
import asyncio
from dotenv import load_dotenv
from google.genai import types


class AgentBrain:
    def __init__(self):
        # Ayarları .env'den çek
        self.use_gemini = os.getenv("USE_GEMINI", "False").lower() == "true"
        self.ollama_model = os.getenv("MODEL", "crypto-agent:gemma") # Fallback
        
        # ORTAK SYSTEM PROMPT (Hem Gemini hem Ollama için)
        self.system_instruction = """
        You are an elite high-frequency crypto trading AI.
        
        CORE RULES:
        1. PAIR SELECTION: I will provide a list of AVAILABLE_COINS. Pick relevant ones based on the news.
        2. INFERENCE: If news says "Satoshi", imply "BTC". If "Vitalik", imply "ETH".
        3. OUTPUT: Return a JSON object with a "trades" list.
        
        JSON STRUCTURE:
        {
          "trades": [
            {
              "symbol": "BTC",
              "action": "LONG" | "SHORT",
              "confidence": 85,
              "tp_pct": 2.5,
              "sl_pct": 1.0,
              "validity_minutes": 15,
              "reason": "Mining upgrade news"
            }
          ]
        }
        """

        if self.use_gemini:
            load_dotenv()
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                print("❌ [HATA] USE_GEMINI=True ama GOOGLE_API_KEY yok!")
                self.use_gemini = False # Fallback to Ollama
            else:
                # Gemini için yapılandırma
                self.gemini_client = genai.client(api_key)
                print(f"🧠 [BEYİN] Mod: GEMINI API ({os.getenv('GEMINI_MODEL')})")
        
        if not self.use_gemini:
            print(f"🧠 [BEYİN] Mod: YEREL OLLAMA ({self.ollama_model})")

    async def analyze(self, news, available_pairs):
        # Coin listesini string'e çevir
        coins_str = ", ".join([p.replace('usdt', '').upper() for p in available_pairs])
        
        # User Prompt (Sadece anlık veriyi içerir)
        user_prompt = f"""
        AVAILABLE_COINS: [{coins_str}]
        NEWS: "{news}"
        
        TASK: Identify impacted coins and decide trades. 
        If no relevant coin found or news is irrelevant, return {{ "trades": [] }}
        """

        try:
            # --- YOL AYRIMI ---
            if self.use_gemini:
                # 1. GEMINI YOLU
                generation_config=types.GenerationConfig(
                        response_mime_type="application/json", # JSON zorlama modu
                        temperature=0.1,
                    )
                response = self.gemini_client.models.generate_content(
                    model= os.getenv('GEMINI_MODEL'),
                    contents = [self.system_instruction, user_prompt, news],
                    config = generation_config
                )
                return json.loads(response.text)
            
            else:
                # 2. OLLAMA YOLU
                # Ollama için system prompt'u user prompt'un içine eklememiz gerekebilir 
                # (eğer modelfile kullanmıyorsak). Ama sen modelfile kullandığın için
                # system prompt zaten modelin içinde var.
                res = await asyncio.to_thread(
                    ollama.chat, 
                    model=self.ollama_model,
                    messages=[{'role': 'user', 'content': user_prompt}],
                    format='json', 
                    options={'temperature': 0.1}
                )
                return json.loads(res['message']['content'])

        except Exception as e:
            print(f"❌ [BEYİN HATASI] Analiz başarısız: {e}")
            return {"trades": []}