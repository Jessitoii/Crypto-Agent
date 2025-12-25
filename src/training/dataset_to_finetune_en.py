import json
import asyncio
import sys
import os
import random
import aiofiles
import re
from groq import AsyncGroq

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQCLOUD_API_KEY

INSTRUCTION = """
You are a Lead Event-Driven Quantitative Trader.
Decisions are based strictly on pre-event information.
Risk preference or narrative style must not affect decisions.

Core Mission:
Identify asymmetric trading edges using strictly pre-event information.
Default stance is NO_TRADE.
Capital preservation overrides opportunity seeking.

Evaluation Protocol:

1) Catalyst DNA:
Determine whether the news is structurally capable of moving an asset of this Market Cap and Category.
Price movement alone is never evidence.

2) Contextual Synthesis:
Evaluate RSI, Funding, and Momentum for signs of positioning imbalance,
liquidity absorption, squeeze risk, or mean reversion pressure.
Momentum without structural support is NOT an edge.

3) Edge Detection:
If and only if an asymmetric edge exists, classify the primary driver as:
Momentum, Liquidity, MeanReversion, NewsDecay, or VolatilityExpansion.

Hard Consistency Rules:

- NO_TRADE -> Edge: None, Horizon: None, Risk Posture: Avoid.
- VALID_TRADE -> Risk Posture must be Moderate or Aggressive.
- Momentum / VolatilityExpansion -> Horizon: Immediate or Short.
- MeanReversion / NewsDecay -> Horizon: Short only.

Constraints:
45–65 words total.
Zero hindsight bias.
No justification based on post-event price action.
If NO_TRADE, explicitly state why a professional desk stays sidelined.

"""

# Config
MODEL_NAME = "llama-3.3-70b-versatile" 
INPUT_FILE = "data/raw_market_outcomes_v1_5.jsonl"
OUTPUT_FILE = "data/synthetic_finetune_data_v2_5.jsonl"

client = AsyncGroq(api_key=GROQCLOUD_API_KEY)


def get_sampling_params(phase, persona):
    if phase == "canonical":
        return {
            "temperature": 0.35 if persona == "risk-averse" else 0.45,
            "top_p": 0.70,
            "frequency_penalty": 1.05,
            "presence_penalty": 0.0
        }
    else:  # stress
        return {
            "temperature": 0.45 if persona != "aggressive" else 0.55,
            "top_p": 0.80,
            "frequency_penalty": 1.08,
            "presence_penalty": 0.15
        }

async def ask_teacher_llm(row, phase="canonical", persona="neutral"):
    d = row['data']
    news = row['news']
    

    # 2️⃣, 3️⃣, 4️⃣, 5️⃣ Düzeltmeler: Edge, Horizon, Consistency ve Risk Posture
    prompt = f"""You are a Lead Event-Driven Quant.
MISSION: Objectively determine if an asymmetric edge exists.

After the decision is fixed, explain the reasoning from a ({persona}) risk perspective.


NEWS: {news}
CONTEXT: {d['symbol']} | {d['category']} | MCAP: {d['market_cap']}
METRICS: RSI: {d['rsi']}, BTC: {d['btc_trend']}%, Funding: {d['funding']}%, Mom: {d['momentum']['1h']}%

CONSISTENCY RULES:
- Momentum / Liquidity / VolatilityExpansion -> Horizon: Immediate or Short.
- MeanReversion / NewsDecay -> Horizon: Short only.
- NO_TRADE Verdict -> Edge: None, Horizon: None, Risk Posture: Avoid.
- VALID_TRADE Verdict -> Risk Posture: Moderate or Aggressive.


ANALYSIS STRUCTURE (Strictly follow this internal logic):
1) Catalyst DNA (Primary Driver): Assess if the news has the structural power to force a price shift given the asset's Market Cap. If the news is "noise" relative to the 1.8T/117B valuation, the verdict is NO_TRADE regardless of metrics.

2) Contextual Friction (The Filter): Use RSI, Funding, and Momentum ONLY to determine if the market is too "tired" or "over-leveraged" to react to the news. Metrics are filters, NOT the reason for the trade.

3) Synthesis Logic: Your reasoning must explain: "The catalyst is [X], and the current market friction (RSI/Funding) [allows/prevents] this move because [Y]."

CONSTRAINTS:
- MINIMUM 120 words of dense, professional technical analysis.
- NO bullet points. Use prose with high semantic density.
- Do NOT repeat the input metrics. Use them to draw conclusions (e.g., instead of "RSI is 80", use "The technical overextension evidenced by an 80+ RSI suggests...").
- ZERO hindsight bias. No "post-event price action" talk.
- Use professional terminology: (e.g., Delta imbalance, Mean reversion pressure, Liquidity absorption, Gamma exposure, Neutralizing positioning).

OUTPUT STRICT JSON:
{{
    "reasoning": "80-120 words contextual synthesis. Analyze the friction between the catalyst's power and the current metrics (RSI/Funding/Mom). Explain why the market [will/won't] absorb this news based ONLY on provided data. No hallucinated metrics.",
    "edge_type": "Momentum|Liquidity|MeanReversion|NewsDecay|VolatilityExpansion|None",
    "trade_horizon": "Immediate|Short|None",
    "risk_posture": "Avoid|Moderate|Aggressive",
    "verdict": "VALID_TRADE|NO_TRADE"
}}"""

    temp_map = {"risk-averse": 0.35, "neutral": 0.45, "aggressive": 0.55}
    
    params = get_sampling_params(phase, persona)
    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            response = await client.chat.completions.create(
                model=MODEL_NAME, 
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                **params
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            error_msg = str(e)

            # --- 429 RATE LIMIT AYIKLAMA MANTIĞI ---
            if "429" in error_msg:
                retries += 1
                # Regex ile bekleme süresini bul (ms veya s)
                # Örn: "Please try again in 690ms" veya "try again in 2s"
                ms_match = re.search(r"try again in (\d+)ms", error_msg)
                sec_match = re.search(r"try again in (\d+)s", error_msg)

                wait_time = 1.0 # Default 1 saniye

                if ms_match:
                    wait_time = float(ms_match.group(1)) / 1000.0
                elif sec_match:
                    wait_time = float(sec_match.group(1))

                # Güvenlik payı ekle (0.2 saniye)
                wait_time += 0.2

                print(f"⏳ [RATE LIMIT] 429 Hata! {wait_time:.2f}s bekleniyor... (Deneme {retries}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue # Döngü başına dön ve tekrar dene
            
            else:
                print(f"❌ [ERROR] LLM Request Failed: {e}")
                return None


async def process_distillation():

    startfrom = 0
    async with aiofiles.open(INPUT_FILE, mode='r', encoding='utf-8') as f:
        lines = await f.readlines()

    async with aiofiles.open(OUTPUT_FILE, mode='a', encoding='utf-8') as out_f:
        for i, line in enumerate(lines):
            if i < startfrom:
                continue
            row = json.loads(line)
            d = row['data']
            URL_REGEX = re.compile(
                r"https?://\S+|www\.\S+",
                re.IGNORECASE
            )
            URL_REGEX2 = re.compile(
                r"http?://\S+|www\.\S+",
                re.IGNORECASE
            )
            def remove_urls(text: str) -> str:
                text = URL_REGEX.sub("", text)
                text = URL_REGEX2.sub("", text)
                return text.strip()

            d['news'] = remove_urls(row['news'])
            row['news'] = d['news']            
            # 2️⃣ Düzeltme: Persona olay bazlı atanır, aynı olaya farklı kararlar verilmesi engellenir.
            persona_roll = random.random()
            persona = "risk-averse" if persona_roll < 0.2 else "aggressive" if persona_roll > 0.8 else "neutral"
            
            phase = "stress" if (
                abs(d['funding']) > 0.05 or
                abs(d['momentum']['1h']) > 1.5 or
                abs(d['btc_trend']) > 1.2
            ) else "canonical"            
            res = await ask_teacher_llm(row, phase=phase, persona=persona)
            
            # 7️⃣ Düzeltme: Async Logging & Safety Check
            verdict = res.get("verdict", "ERR") if res else "ERR"
            
            if res and verdict != "ERR":
                # Semantik Doğrulama (Post-processing)
                if verdict == "NO_TRADE":
                    res["risk_posture"] = "Avoid"
                    res["edge_type"] = "None"
                    res["trade_horizon"] = "None"

                instructions = {
                    "risk-averse": "Acting as a conservative Quant, prioritize capital preservation.",
                    "neutral": "Acting as a Quant Strategist, perform objective event synthesis.",
                    "aggressive": "Acting as a high-alpha Quant, seek aggressive entries."
                }

                entry = {
                    "instruction": INSTRUCTION.format(persona=persona),
                    "input": f"News: {row['news']}\nContext: {d['symbol']} | {d['category']} | {d['market_cap']}\nMetrics: RSI {d['rsi']} | BTC {d['btc_trend']}% | Funding: {d['funding']}% | Momentum(1 hour): {d['momentum']['1h']}% ",
                    "output": {
                        "analysis": res["reasoning"],
                        "edge": res["edge_type"],
                        "decision": verdict,
                        "horizon": res["trade_horizon"],
                        "posture": res["risk_posture"]
                    }
                }
                await out_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
            sys.stdout.write(f"\r🚀 {i+1}/{len(lines)} | P: {persona[:4]} | V: {verdict}")
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(process_distillation())