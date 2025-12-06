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
<<<<<<< HEAD
        self.use_gemini = False
        self.ollama_model = "crypto-agent:gemma" # Fallback
=======
        self.use_gemini = os.getenv("USE_GEMINI", "False").lower() == "true"
        self.ollama_model = os.getenv("MODEL", "crypto-agent:gemma") # Fallback
>>>>>>> origin
        
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
<<<<<<< HEAD
        """

        if self.use_gemini:
            load_dotenv()
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                print("❌ [HATA] USE_GEMINI=True ama GOOGLE_API_KEY yok!")
                self.use_gemini = False # Fallback to Ollama
            else:
                # Gemini için yapılandırma
                self.gemini_client = genai.Client(api_key=api_key)
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
                generation_config=types.GenerateContentConfig(
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
        
    async def analyze_specific(self, news, symbol, price, change_1m):
        """
        Sadece önceden tespit edilmiş TEK BİR coin için analiz yapar.
        """
        prompt = f"""
        DETECTED COIN: {symbol.upper()}
        PRICE CHANGE (1min): {change_1m}%
        CURRENT PRICE: {price}
        NEWS: "{news}"
        
        YOUR MISSION:
        1. VALIDATION: Does the news actually mention/imply {symbol.upper()}? If not, ACTION: HOLD.
        2. ANALYSIS: Analyze sentiment (Positive/Negative).
        3. MOMENTUM CHECK: 
           - If news is BULLISH but price already pumped > 3%, risk is high (FOMO). Consider HOLD or strict SL.
           - If news is BULLISH and price is stable/dipping, it's a good entry.
        
        JSON OUTPUT ONLY:
        {{
            "action": "LONG" | "SHORT" | "HOLD",
            "confidence": <int 0-100>,
            "tp_pct": <float>,
            "sl_pct": <float>,
            "validity_minutes": <int>,
            "reason": "<Explain logic based on news AND price change>"
        }}
=======
>>>>>>> origin
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
<<<<<<< HEAD
            # Gemini veya Ollama kullanımı (Senin konfigürasyonuna göre)
            # Burası senin mevcut yapına göre hibrit çalışır
            if self.use_gemini: # Eğer Gemini aktifse
                response = await self.gemini_client.generate_content_async(prompt)
                return json.loads(response.text)
            else: # Ollama aktifse
                res = await asyncio.to_thread(
                    ollama.chat, 
                    model=self.ollama_model,
                    messages=[{'role': 'user', 'content': prompt}],
                    format='json', 
                )
                return json.loads(res['message']['content'])
                
        except Exception as e:
            print(f"[HATA] LLM Analizi: {e}")
            return {"action": "HOLD", "confidence": 0, "reason": "Error"}
        
    async def detect_symbol(self, news, available_pairs):
        """
        Regex başarısız olduğunda LLM'den sembol bulmasını ister.
        """
        # Sadece coin listesini string yap (USDT olmadan)
        coins_str = ", ".join([p.replace('usdt', '').upper() for p in available_pairs])
        
        prompt = f"""
        TASK: Identify the cryptocurrency symbol in this news.
        NEWS: "{news}"
        ALLOWED SYMBOLS: [{coins_str}]
        
        RULES:
        1. If the news talks about "Satoshi" or "Bitcoin", return "BTC".
        2. If news talks about "Ether", return "ETH".
        3. Only return a symbol if it exists in ALLOWED SYMBOLS list.
        4. If no specific coin is found, return null.
        
        JSON OUTPUT ONLY:
        {{
            "symbol": "BTC" | null
        }}
        """
        try:
            # Gemini veya Ollama kullanımı (Mevcut yapına göre)
            if hasattr(self, 'gemini_client') and self.use_gemini:
                response = await self.gemini_client.generate_content_async(prompt)
                res_json = json.loads(response.text)
            else:
                res = await asyncio.to_thread(
                    ollama.chat, 
                    model=self.ollama_model,
                    messages=[{'role': 'user', 'content': prompt}],
                    format='json', 
                    options={'temperature': 0.0} # Sıfır yaratıcılık
                )
                res_json = json.loads(res['message']['content'])
            
            return res_json.get('symbol')
            
        except Exception as e:
            print(f"[HATA] Sembol Tespiti: {e}")
            return None
=======
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
>>>>>>> origin
