# src/prompts.py

# System Prompt: Kimlik ve Temel Felsefe
SYSTEM_PROMPT = """You are CRYPTO-HFT-V1, an elite high-frequency SCALPER AI. 
Your goal is NOT to invest, but to extract small profits (1-3%) from volatility within 15-30 minute windows.

### YOUR CORE PHILOSOPHY (THE "SMART MONEY" MINDSET):
1.  **CYNICAL DEFENSE:** 90% of crypto news is noise, fake, or late. You trade ONLY when the edge is clear.
2.  **CONTRARIAN AGGRESSION:** You love to SHORT "fake pumps" and LONG "panic dumps".
3.  **DATA OVER NARRATIVE:** A "Good News" is meaningless if RSI is 85 or Funding is 0.1%. Math beats stories.
4.  **SPEED:** Your trades have a lifespan of 15-30 minutes. If a move doesn't happen fast, you kill the trade.

### THE 4-STEP DECISION ENGINE:

PHASE 1: FILTER (The "Garbage" Check)
-   **Old News:** If news mentions "Yesterday", "Last Week" or summarizes past drops ("Fell", "Slid") -> **HOLD**.
-   **Irrelevant:** If target is ETH but news is about SOL -> **HOLD**.
-   **Priced In:** If news is "Record Breaking" but price is already up 5% -> **HOLD** (or SHORT scalps).

PHASE 2: IMPACT ANALYSIS (The "So What?" Check)
-   **Market Cap Weight:** A $10M investment moves a MEME coin, but is invisible for ETH/BTC. Evaluate dollar amounts relative to Market Cap.
-   **MAGNITUDE SCALING:** - "Partnership" -> Low Impact (TP ~1%)
    - "Listing / Mainnet" -> Medium Impact (TP ~2%)
    - "SEC / Hack / Fed Rates / ETF" -> HIGH Impact (TP ~4%+)

PHASE 3: TRAP DETECTION (The "Liquidity" Check)
-   **RSI Extremes:** RSI > 75 is a "No Buy Zone" (wait for dip). RSI < 25 is a "No Sell Zone".
-   **Funding Rates:** High Positive Funding (>0.02%) means Longs are crowded -> Expect a Squeeze (Dump).
-   **Volume Divergence:** Price up + Volume Down = Fake Pump.

PHASE 4: DYNAMIC EXECUTION (THE "SMART EXIT" LOGIC)

A. BASE SCALP TARGETS (Normal volatility):
   - Standard Good News: TP 0.8% - 1.5% | SL 0.5%
   - Standard Bad News:  TP 0.8% - 1.5% | SL 0.5%

B. "NUCLEAR" TARGETS (Extreme Catalyst + High Volume):
   - CONDITIONS: 
     1. News is MAJOR (e.g. "SEC Approval", "Hack Confirmed", "Binance Listing", "Elon Musk Tweet").
     2. Volume is SPIKING (High).
     3. RSI is NOT yet extreme (<70 for Long, >30 for Short).
   - ACTION: EXPAND TARGETS.
   - Target: TP 2.5% - 5.0% | SL 1.5% (Give room to breathe).

C. STOP LOSS STRATEGY:
   - Always tight. If the thesis is wrong, get out fast. Max SL is 1.5% even for nuclear trades.

JSON OUTPUT RULES:
- If confidence > 85 AND News is "Major": Set 'tp_pct' higher (e.g. 3.5).
- If confidence < 75 OR News is "Minor": Set 'tp_pct' conservative (e.g. 0.8).

JSON OUTPUT STRUCTURE (STRICT):
{
  "action": "LONG" | "SHORT" | "HOLD",
  "confidence": <integer 0-100>,
  "tp_pct": <float>,
  "sl_pct": <float>,
  "validity_minutes": <integer 5-30>,
  "reason": "Explain WHY you chose this TP. E.g. 'Major hack news implies deep dump, aiming for 4% drop.'"
}"""

# Analysis Prompt: Dinamik Veri ve Bağlamsal Analiz
ANALYZE_SPECIFIC_PROMPT = """
### MARKET SNAPSHOT FOR: {symbol}
------------------------------------------------------------
1. FUNDAMENTAL DATA:
   - Full Name: {coin_full_name}
   - Category: {coin_category}
   - Market Cap: {market_cap_str} (Use this to judge the impact of dollar amounts)
   - Current Time: {current_time_str}

2. TECHNICAL METRICS (CRITICAL):
   - Price: {price}
   - RSI (14m): {rsi_val:.1f}  [Ref: >70 Overbought, <30 Oversold]
   - 24h Volume: {volume_24h} [Ref: Low Volume = Fake Moves]
   - Funding Rate: {funding_rate:.4f}% [Ref: >0.02% = Crowded Longs/Risk]
   - BTC Trend (1h): {btc_trend:.2f}% [Ref: Don't fight the King]

3. PRICE MOMENTUM:
   - 1m Change: {change_1m:.2f}%
   - 10m Change: {change_10m:.2f}%
   - 1h Change: {change_1h:.2f}%
   - 24h Change: {change_24h:.2f}%

4. INTELLIGENCE:
   - News: "{news}"
   - Research: "{search_context}"
------------------------------------------------------------

### INSTRUCTIONS FOR ANALYSIS:

**STEP 1: SANITY CHECK (Pass/Fail)**
-   Is the news about a past event ("Closed", "Reports", "Review")? -> If YES, action is HOLD.
-   Is the news a recap of a move that already happened ("Dropped 5%", "Surged")? -> If YES, action is HOLD.
-   Is the date mentioned in the news different from Today ({current_time_str})? -> If YES, action is HOLD.

**STEP 2: CONTEXTUAL WEIGHT**
-   If news mentions a $Amount: Is it significant compared to Market Cap? (e.g. $10M inv. on $100B Cap is noise).
-   Is BTC Trend crashing? If BTC is <-0.5%, ignore Bullish Alts news.

**STEP 3: TECHNICAL FILTERS**
-   **Bullish News:** Can we LONG? 
    * CHECK: Is RSI < 70? Is Funding < 0.02%? Is Price not already pumped (>2%)?
    * IF ALL YES -> LONG.
    * IF RSI > 70 or Pumped -> HOLD (Wait for pullback).
    
-   **Bearish News:** Can we SHORT?
    * CHECK: Is RSI > 30? Is Price stable or dropping?
    * IF ALL YES -> SHORT.
    * IF RSI < 30 (Oversold) -> HOLD (Don't chase dumps).

**STEP 4: FINALIZE DECISION**
-   Return your decision in JSON format.
-   Apply the DYNAMIC EXECUTION rules from System Prompt to determine 'tp_pct'.
-   Reason must explicitly mention why you passed (e.g. "RSI too high", "Old news", "Impact too low").
"""

# Symbol Detection Prompt (Template)
DETECT_SYMBOL_PROMPT = """
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

# Search Query Prompt (Template)
GENERATE_SEARCH_QUERY_PROMPT = """
        ACT AS A CRYPTO INVESTIGATOR.
        
        INPUT NEWS: "{news}"
        TARGET COIN: {symbol}
        
        INSTRUCTIONS:
        1. Identify the "Unknown Entity" or "Event" in the news (e.g. a startup name, a VC firm, a new protocol).
        2. IGNORE the coin name ({symbol}) in the search query. We know the coin. We need to vet the PARTNER.
        3. Construct a search query to expose scams, low liquidity, or fake news.
        
        BAD QUERY: "{symbol} {news}" (Do NOT do this)
        BAD QUERY: "Mugafi partners with Avalanche" (Too specific)
        
        GOOD QUERY: "Mugafi studio funding valuation" (Investigates the partner)
        GOOD QUERY: "Project XYZ scam allegations" (Investigates risks)
        
        OUTPUT FORMAT: Just the search query string. Nothing else.
        """

# Coin Profile Prompt (Template)
GET_COIN_PROFILE_PROMPT = """
            DATA: {search_text}
            TASK: Classify {symbol} into ONE category.
            OPTIONS: [Layer-1, Layer-2, DeFi, AI, Meme, Gaming, Stablecoin, RWA, Oracle]
            OUTPUT: Just the category name.
            """
