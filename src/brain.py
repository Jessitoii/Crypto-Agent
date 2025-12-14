import json
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from groq import AsyncGroq
import ollama
# Yerel modüller
from config import llm_config
from utils import search_web_sync, coin_categories
import time
import re

class AgentBrain:
    def __init__(self, use_groqcloud=True, api_key=None, groqcloud_model="google/gemini-2.0-flash-exp:free"):
        self.use_groqcloud = use_groqcloud
        self.model = groqcloud_model
        self.ollama_model = "crypto-agent:gemma"  # Fallback
        self.api_key = api_key
        self.coin_cache = {} # Cache'i başta tanımla
        self.last_request_time = 0
        # Dakikada 1 istek için 60sn. Güvenlik payı ile 62sn yapıyoruz.
        self.MIN_REQUEST_INTERVAL = 62

        # 1. OpenRouter (GroqCloud) Kurulumu
        if self.use_groqcloud:
            print(f"🧠 [BEYİN] Mod: OPENROUTER ({self.model})")
            self.client = AsyncGroq(
                api_key=self.api_key,
            )
        
        # 2. Yerel Ollama Kurulumu (Fallback)
        else:
            print(f"🧠 [BEYİN] Mod: YEREL OLLAMA ({self.ollama_model})")
            print("🔥 [SİSTEM] Model VRAM'e yükleniyor ve kilitleniyor (Keep-Alive)...")
            try:
                ollama.chat(model=self.ollama_model, messages=[{'role': 'user', 'content': 'hi'}], keep_alive=-1)
                print("✅ [SİSTEM] Model yüklendi ve hazır!")
            except Exception as e:
                print(f"⚠️ Model yükleme uyarısı: {e}")

    async def _wait_for_rate_limit(self):
        """
        GroqCloud TPM limitini aşmamak için zorunlu bekleme süresi.
        Son istekten bu yana 62 saniye geçmediyse, kalan süre kadar uyur.
        """
        if not self.use_groqcloud:
            return

        current_time = time.time()
        time_diff = current_time - self.last_request_time

        if time_diff < self.MIN_REQUEST_INTERVAL:
            sleep_time = self.MIN_REQUEST_INTERVAL - time_diff
            print(f"⏳ [KOTA KORUMASI] {sleep_time:.1f} saniye soğuma bekleniyor...")
            await asyncio.sleep(sleep_time) # Kodun geri kalanını bloklamadan bekle
        
        # Zamanı güncelle
        self.last_request_time = time.time()

    def _clean_thinking(self, text):
        """
        Modelin <think>...</think> arasındaki sesli düşünme kısımlarını temizler.
        """
        if not text:
            return ""
        
        # re.DOTALL: Nokta (.) karakterinin yeni satırları da kapsamasını sağlar.
        # Böylece çok satırlı düşünme blokları da silinir.
        pattern = r"<think>.*?</think>"
        cleaned_text = re.sub(pattern, "", text, flags=re.DOTALL)
        
        return cleaned_text.strip()

    async def _submit_to_llm(self, prompt, temperature=0.1, json_mode=True, max_tokens=1024, use_system_prompt=True, reasoning_mode="none"):
        """
        MERKEZİ LLM ÇAĞRI FONKSİYONU
        Tekrarlanan kodları engellemek için tüm istekler buradan geçer.
        """
        try:
            # --- 1. Mesaj Listesini Temiz Oluştur ---
            # Hatayı çözen kısım burası: Listeye None eklemiyoruz.
            messages_payload = []
            
            if use_system_prompt:
                messages_payload.append({"role": "system", "content": llm_config['system_prompt']})
            
            messages_payload.append({"role": "user", "content": prompt})

            # --- A. OPENROUTER / GROQ ---
            if self.use_groqcloud:
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages_payload, # Temiz liste
                    response_format={"type": "json_object"} if json_mode else None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    reasoning_effort=reasoning_mode
                )
                raw_response = completion.choices[0].message.content
                cleaned_response = self._clean_thinking(raw_response)
                return cleaned_response
            # --- B. OLLAMA ---
            else:
                options = {
                    'temperature': temperature,
                    'num_ctx': 512, 
                    'num_predict': 128 if not json_mode else 32
                }
                res = await asyncio.to_thread(
                    ollama.chat,
                    model=self.ollama_model,
                    messages=messages_payload, # Temiz liste
                    format='json' if json_mode else '',
                    options=options,
                    keep_alive=-1
                )
                return res['message']['content']

        except Exception as e:
            print(f"❌ [HATA] LLM İsteği Başarısız: {e}")
            return None

    async def analyze_specific(self, news, symbol, price, changes, search_context="", coin_full_name="Unknown"):
        # 1. Profil Bilgisi
        await self._wait_for_rate_limit()
        coin_category = await self.get_coin_profile(symbol)
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"🐛 [DEBUG] {symbol} Kategorisi: '{coin_category}'")
        print(f"🐛 [DEBUG] Fiyat: {price}, Değişimler: {changes}")

        prompt = f"""
        TARGET COIN: {symbol.upper()}
        COIN FULL NAME: {coin_full_name}
        OFFICIAL CATEGORY: {coin_category} (TRUST THIS CATEGORY ABSOLUTELY!)
        CURRENT SYSTEM TIME: {current_time_str} (This is "NOW")

        MARKET MOMENTUM:
        - Price: {price}
        - 1m Change: {changes['1m']:.2f}%
        - 10m Change: {changes['10m']:.2f}%
        - 1h Change: {changes['1h']:.2f}%
        - 24h Change: {changes['24h']:.2f}%
        
        NEWS SNIPPET: "{news}"
        RESEARCH CONTEXT: "{search_context}"

        ROLE: You are an AGGRESSIVE SCALPER. Do not hold positions.
        
        CRITICAL RULES (PRIORITY 1):
        1. IDENTITY: If TARGET COIN is 'ETH' (Layer-1), do NOT treat it as 'Stablecoin' even if news mentions USDT.
        2. RELEVANCE: Ensure news is specifically about {symbol.upper()}. Ignore generic market news unless it's a massive crash/pump.
        3. TIME & DATE CHECK (CRUCIAL): 
         - Compare CURRENT SYSTEM TIME with any date mentions in the NEWS.
         - If news talks about "Yesterday", "Last Week", or a specific date that is NOT today (e.g., News date is Dec 9, Today is Dec 10) -> THIS IS STALE DATA.
         - STALE DATA ACTION: HOLD (Do not trade old news).
         - Exception: Unless it mentions "Upcoming" or "Future" events for that date.
         
        TRADING LOGIC (PRIORITY 2):
        A. SHORT SIGNALS (Don't be afraid to short):
           - News = "Hack", "Exploit", "Delay", "Scam", "Investigation", "Sell-off".
           - News = "Good/Neutral" BUT Price is DROPPING (1m < -0.5%) -> Trend Reversal Short.
           - News = "Bad" AND Price is PUMPING -> Top Short Opportunity.
           
        B. LONG SIGNALS:
           - News = "Major Partnership", "ETF Approval", "Listing", "Mainnet".
           - ONLY if Price is STABLE (-0.5% to +0.5%) or DIPPING. 
           - IF Price > +2.0% (1m/10m) -> HOLD (FOMO Trap).
           
        C. TIME MANAGEMENT:
           - MAX VALIDITY: 30 Minutes. NO EXCEPTIONS.
           - Ideal Validity: 10-15 Minutes.
           
        RULES FOR TIMING:
        - CHECK VERB TENSE: Is the news about something that ALREADY happened ("Sold off", "Dropped", "Plunged")?
          -> IF YES: The move is likely over. ACTION: HOLD (Don't chase ghosts).
        - Is the news about something HAPPENING NOW or COMING ("Launching", "Partnering", "Approving")?
          -> IF YES: ACTION: LONG/SHORT.
        
        JSON OUTPUT ONLY:
        {{
            "action": "LONG" | "SHORT" | "HOLD",
            "confidence": <int 0-100>,
            "tp_pct": <float 1.5-4.0>,
            "sl_pct": <float 0.5-1.5>,
            "validity_minutes": <int 5-30>,
            "reason": "SHORT because bad news and price weakness. Time limited to 15m."
        }}
        """

        response_text = await self._submit_to_llm(prompt, temperature=0.1, json_mode=True, max_tokens=2048, use_system_prompt=True, reasoning_mode="default")
        
        try:
            return json.loads(response_text)
        except Exception:
            return {"action": "HOLD", "confidence": 0, "reason": "Error parsing JSON"}

    async def detect_symbol(self, news, available_pairs):
        prompt = f"""
        TASK: Identify which cryptocurrency symbol is most impacted by this news.
        NEWS: "{news}"
        
        RULES:
        1.  **IMPACT ANALYSIS:** Determine which specific cryptocurrency's price or sentiment is most likely to be affected by this news.
        2.  **INFERENCE:**
            * If the news mentions "Satoshi", "Bitcoin", or general crypto market trends led by Bitcoin, return "BTC".
            * If the news mentions "Vitalik", "Ether", or Ethereum ecosystem updates, return "ETH".
            * If the news mentions a project built on a specific chain (e.g., "Jupiter on Solana"), return the chain's token if the project token isn't listed (e.g., "SOL").
        3.  **CONSTRAINT:** Only return a symbol if it exists in the ALLOWED SYMBOLS list.
        4.  **NULL:** If no specific coin from the list is impacted, return null.
        
        JSON OUTPUT ONLY:
        {{
            "symbol": "BTC" | null
        }}
        """
        
        response_text = await self._submit_to_llm(prompt, temperature=0.0, json_mode=True, max_tokens=16, use_system_prompt=False)
        
        try:
            res_json = json.loads(response_text)
            return res_json.get('symbol')
        except Exception as e:
            print(f"[HATA] Sembol Tespiti JSON hatası: {e}")
            return None

    async def generate_search_query(self, news, symbol):
        prompt = f"""
        ACT AS A CRYPTO INVESTIGATOR.
        
        INPUT NEWS: "{news}"
        TARGET COIN: {symbol.upper()}
        
        INSTRUCTIONS:
        1. Identify the "Unknown Entity" or "Event" in the news (e.g. a startup name, a VC firm, a new protocol).
        2. IGNORE the coin name ({symbol.upper()}) in the search query. We know the coin. We need to vet the PARTNER.
        3. Construct a search query to expose scams, low liquidity, or fake news.
        
        BAD QUERY: "{symbol} {news}" (Do NOT do this)
        BAD QUERY: "Mugafi partners with Avalanche" (Too specific)
        
        GOOD QUERY: "Mugafi studio funding valuation" (Investigates the partner)
        GOOD QUERY: "Project XYZ scam allegations" (Investigates risks)
        
        OUTPUT FORMAT: Just the search query string. Nothing else.
        """
        
        # Sıcaklığı biraz artırıyoruz (0.7)
        response_text = await self._submit_to_llm(prompt, temperature=0.7, json_mode=False, max_tokens=64, use_system_prompt=False, reasoning_mode="none")
        return response_text.strip()

    async def get_coin_profile(self, symbol):
        sym = symbol.upper().replace('USDT', '')
        
        # 1. HIZLI LİSTE
        if sym in coin_categories:
            return coin_categories[sym]

        # 2. CACHE KONTROLÜ
        if sym in self.coin_cache:
            return self.coin_cache[sym]

        # 3. INTERNET ARAMASI & LLM
        print(f"🔍 [BEYİN] {sym} bilinmiyor, internetten öğreniliyor...")
        query = f"what is {sym} crypto category sector utility"
        
        try:
            search_text = await asyncio.to_thread(search_web_sync, query)
            
            profile_prompt = f"""
            DATA: {search_text}
            TASK: Classify {sym} into ONE category.
            OPTIONS: [Layer-1, Layer-2, DeFi, AI, Meme, Gaming, Stablecoin, RWA, Oracle]
            OUTPUT: Just the category name.
            """
            
            # Burada JSON mode kapalı olabilir çünkü sadece tek kelime istiyoruz
            category = await self._submit_to_llm(profile_prompt, temperature=0.0, json_mode=False, max_tokens=256, use_system_prompt=False)
            category = category.strip()
            
            # Cache'e kaydet
            self.coin_cache[sym] = category
            print(f"🧬 [PROFİL] {symbol} sınıflandırıldı: {category}")
            return category

        except Exception as e:
            print(f"Profil Hatası: {e}")
            return "Unknown"