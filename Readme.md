# Crypto HFT AI Agent 🤖

**An elite, high-frequency cryptocurrency trading bot powered by Large Language Models (LLMs), autonomous web research, and real-time market sentiment analysis.**

This agent doesn't just read news; it **thinks**, **researches**, and **decides**. It combines technical market data (Websockets) with fundamental analysis (Telegram News + DuckDuckGo Research) to execute trades with surgical precision on Binance Futures.

---

## 🚀 Key Features

* **🧠 Hybrid AI Brain:**
    * Supports both **Local Inference** (Ollama/Gemma) for privacy and zero-cost.
    * Supports **Google Gemini API** for high-speed, cloud-based reasoning.
    * Uses **Chain-of-Thought** prompting to analyze news sentiment, magnitude, and credibility.

* **🕵️‍♂️ Autonomous Detective Mode:**
    * Doesn't blindly trust news. Automatically generates search queries and uses **DuckDuckGo** to verify unknown projects, check for scams, or validate partnership claims before trading.

* **⚡ Real-Time Data Pipeline:**
    * **WebSocket Stream:** Listens to real-time `kline_1m` and `24h_ticker` data from Binance.
    * **Backfill System:** Automatically fetches missing historical data from the API if the local buffer is empty.
    * **Telegram Listener:** Monitors top crypto news channels instantly via Telethon.

* **🛡️ Advanced Risk Management:**
    * **Coin Profiling:** Automatically classifies coins (e.g., L1, Meme, Stablecoin) to prevent logical errors (like buying ETH because of a USDT news).
    * **Momentum Checks:** Prevents FOMO by checking price changes (1m, 10m, 24h) against news sentiment.
    * **Simulation & Real Modes:** Includes a full **Paper Trading** engine to test strategies without risk, synchronized with a **Real Trading** engine for execution.

* **🎓 Self-Learning (Hindsight Experience Replay):**
    * Automatically logs every decision, market condition, and trade outcome.
    * Generates a `fine_tune_dataset.jsonl` file to train the model on its own mistakes and successes.

---

## 📂 Project Structure

```text
crypto-hft-bot/
├── main.py                 # 🎮 Orchestrator: Manages UI, loops, and threads.
├── brain.py                # 🧠 AI Logic: Prompts, Research, and Decision making.
├── exchange.py             # 📝 Paper Simulation: Manages virtual wallet & PnL.
├── binance_client.py       # 🏦 Real Execution: Binance Futures API adapter.
├── price_buffer.py         # 📊 Memory: Holds recent candles and price changes.
├── data_collector.py       # 💾 Observer: Temporarily logs events for analysis.
├── dataset_manager.py      # 📚 Teacher: Creates training datasets from results.
├── utils.py                # 🛠️ Tools: Web search (DDGS), Coin mapping, etc.
└── .env                    # 🔑 Config: API Keys and settings.
```
🛠️ Installation
----------------

### 1\. Prerequisites

*   Python 3.10+
    
*   [Ollama](https://ollama.com/) (if using local models)
    
*   A Telegram Account (App ID/Hash)
    
*   Binance Futures Account (Testnet recommended first)
    

### 2\. Clone & Install

```
Bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   git clone [https://github.com/yourusername/crypto-hft-bot.git](https://github.com/yourusername/crypto-hft-bot.git)  cd crypto-hft-bot  pip install -r requirements.txt   ```

### 3\. Setup Environment Variables

Create a .env file in the root directory and fill in your credentials:

Ini, TOML

```Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   # --- BINANCE KEYS (Testnet Recommended) ---  BINANCE_API_KEY_TESTNET=your_testnet_key  BINANCE_API_SECRET_TESTNET=your_testnet_secret  # --- TELEGRAM API (my.telegram.org) ---  API_ID=12345678  API_HASH=your_telegram_hash  TELETHON_SESSION_NAME=crypto_agent_session  # --- AI SETTINGS ---  # Set TRUE for Gemini, FALSE for local Ollama  USE_GEMINI=False  GOOGLE_API_KEY=your_gemini_key  MODEL=gemma3:12b  GEMINI_MODEL=gemini-1.5-flash  # --- SYSTEM ---  BASE_URL=wss://[stream.binance.com:9443/stream?streams=](https://stream.binance.com:9443/stream?streams=)   `

### 4\. Setup AI Model (If using Ollama)

If you are running locally, create the custom model:

Bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   ollama pull gemma2:9b  # or gemma3  ollama create crypto-agent -f crypto-agentModelfile.txt   `

🖥️ Usage
---------

Run the main script to start the Dashboard and the Bot:

Bash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   python main.py   `

*   **Dashboard:** Open your browser at http://localhost:8080.
    
*   **Controls:** You can Pause/Start the bot via the UI.
    
*   **Manual Injection:** You can manually type fake news into the UI input box to test the AI's reaction without waiting for Telegram.
    

📊 Logic Flow
-------------

1.  **Event:** A message arrives from Telegram (e.g., "Mugafi partners with AVAX").
    
2.  **Filter:** Regex checks if AVAX is in our target list.
    
3.  **Backfill:** If AVAX price data is missing in RAM, it's fetched from Binance API.
    
4.  **Research:** The Brain generates a query (e.g., _"Mugafi studio valuation"_) and searches the web.
    
5.  **Analysis:** LLM evaluates News + Price Momentum + Research Context.
    
    *   _Result:_ "Mugafi is a small startup. Impact low. Price stable. **HOLD**."
        
6.  **Execution:** If confidence > 75% and Action is LONG/SHORT, the trade is executed on Paper Exchange (and Real Exchange if enabled).
    
7.  **Learning:** Once the trade closes, the result (Profit/Loss) is logged to fine\_tune\_dataset.jsonl to improve the model later.
    

⚠️ Disclaimer
-------------

**This software is for educational purposes only.** Cryptocurrency trading involves high risk. The developers are not responsible for any financial losses incurred while using this bot. Always test thoroughly on **Testnet** before risking real funds.