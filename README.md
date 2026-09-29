# 🌾 Vyapaar Sahayak

**AI-Driven Hyper-Local Business Advisory and Financial Structuring Assistant for Rural Micro-Entrepreneurs**

> "We don't just record business data. We turn business data into clear decisions."

---

## 1. Problem Statement

Rural and semi-urban micro-entrepreneurs in India — kirana store owners, dairy businesses, food stall
operators, tailors, repair shops, and street vendors — run their business on memory and instinct, not
spreadsheets. They rarely get a clear, jargon-free answer to simple questions like *"Is my business
healthy?"*, *"Should I buy more stock?"*, or *"Can I afford a loan right now?"* — and government schemes
meant to help them are scattered, hard to navigate, and hard to trust.

## 2. Solution

Vyapaar Sahayak is a business co-pilot that takes a handful of numbers a shop owner already knows
(sales, expenses, stock, credit, cash, loan) and turns them into:

- An explainable **Business Health Indicator** (five sub-scores — Sales, Cash Flow, Inventory, Credit,
  Debt — each rated Excellent/Good/Average/Poor/Very Poor with a plain-language "why")
- A prioritised, plain-language list of **what to do next**, plus week-over-week **▲/▼ change indicators**
  on every headline number (sales, expenses, surplus, cash, credit)
- A **Financial Structuring Assistant** for figuring out how much money is actually needed, and for what
- **Inventory insights** — fast/slow movers, margins, restocking suggestions
- **Hyper-local Business Intelligence** — live weather (Open-Meteo, no API key needed) combined with a
  curated season/festival/consumer-trend dataset, distilled into a rule-based **AI Business Analysis**
  (summary, opportunities, recommended actions, timing, risks) — clearly labelled as decision support,
  never a guaranteed forecast
- A curated **government scheme finder** — never claims automatic eligibility
- A **weekly action plan** that persists and tracks progress
- A **Business Scenario Simulator** — "what if I collect ₹20,000 credit / take a ₹50,000 loan / sales fall 10%?"
- An optional AI chat layer (Gemini or OpenAI) that explains the numbers — it never invents them

## 3. Key Design Principle: Explainable, Not Magical

The calculation engine (`services/business_analysis.py`, `services/recommendation_engine.py`,
`services/financial_planner.py`, `services/live_opportunity_service.py`) is the **single source of
truth** for every number and every piece of analysis shown anywhere in the app — including the "AI
Business Analysis" on the Opportunities page, which is rule-based and fully explainable, not an LLM
call. The optional LLM chat layer (Ask Vyapaar Sahayak) is only ever allowed to explain, prioritise,
simplify, and personalise — never to invent a financial figure. This is enforced structurally: the LLM
is handed a `BUSINESS_CONTEXT` JSON object and instructed never to introduce numbers not present in it.

## 4. Architecture

```
Vyapaar_Sahayak/
├── app.py                        # Entry point: boot, onboarding, sidebar nav, page dispatch
├── database/
│   └── db.py                     # SQLite schema + all CRUD operations
├── services/                     # Pure-Python business logic (no Streamlit dependency — unit-testable)
│   ├── business_analysis.py      # Ratios, 5-part health score, explainability, scenario simulator
│   ├── recommendation_engine.py  # Structured context builder + rule-based recommendations
│   ├── financial_planner.py      # Capital allocation, EMI estimate, affordability, working-capital gap
│   ├── inventory_service.py      # Margins, fast/slow classification, moving-average demand
│   ├── scheme_service.py         # Government scheme directory + filtering
│   ├── live_opportunity_service.py # Live weather (Open-Meteo) + curated hyper-local signals
│   │                              # + rule-based "AI Business Analysis" generator
│   └── llm_service.py            # Gemini / OpenAI / Smart Demo Mode abstraction (chat only)
├── app_pages/                    # App-controlled page modules, each exposing render()
│   ├── dashboard.py
│   ├── business_insights.py      # Explainability + Scenario Simulator
│   ├── ai_advisor.py             # Ask Vyapaar Sahayak (chat)
│   ├── financial_planner.py
│   ├── inventory_insights.py
│   ├── opportunities.py          # Schemes + Hyper-local Business Intelligence
│   ├── weekly_action_plan.py
│   └── business_profile.py
├── utils/
│   ├── constants.py               # Shared lists, demo data, disclaimer text
│   ├── helpers.py                 # money(), pct(), safe_div(), etc.
│   └── bootstrap.py                # Shared session/DB init, get_context(), global CSS/theme
├── data/
│   ├── schemes.json                # Curated real government schemes with official URLs
│   ├── demo_inventory.json         # Sample products with sales history
│   └── hyperlocal_signals.json     # Crop-cycle / festival / consumer-trend dataset, by state
├── .streamlit/config.toml
├── requirements.txt
├── .env.example
└── README.md
```

## 5. Tech Stack

- **Python 3.9+**
- **Streamlit** — UI framework, custom-themed via `.streamlit/config.toml` + `utils/bootstrap.py`
- **SQLite** (via `sqlite3`, stdlib) — local persistence, no server required
- **Pandas** — tabular data
- **Plotly** — charts (bar, pie, radar)
- **python-dotenv** — `.env` loading (`load_dotenv()` is called at the top of `app.py`)
- **google-generativeai** / **openai** — optional, only used if an API key is set 

## 6. Installation & Running (Windows)

1. Install Python 3.9 or later from [python.org](https://python.org) (tick "Add to PATH" during install).
2. Open **Command Prompt** or **PowerShell** in the project folder.
3. Create and activate a virtual environment (recommended):
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. (Optional) Copy `.env.example` to `.env` and add a `GEMINI_API_KEY` or `OPENAI_API_KEY` if you want
   real AI chat responses instead of Smart Demo Mode. Never commit `.env` — it's already in `.gitignore`.
6. Run the app:
   ```
   python -m streamlit run app.py
   ```
7. Your browser will open automatically at `http://localhost:8501`. On first launch, choose
   **Load demo business** to explore the full app instantly, or **Create my own business**.

The app works completely — every page, every feature — with **no API key at all**, using **Smart Demo
Mode** for the chat page, and the fully rule-based engine for everything else (health score, dashboard,
hyper-local intelligence, financial planner).

## 7. Demo Mode

- **Load demo business** seeds a realistic profile (Rehan Ahmed, Rehan Tailor Shop, Tailoring,
  Kharar, Punjab) with two months of financial snapshots (so the dashboard's ▲/▼ change indicators
  have something to compare against), a 10-product inventory catalogue with sales history, and an
  auto-generated weekly action plan.
- **Reset demo data** (sidebar) wipes everything and returns to the onboarding screen.

## 8. AI Chat Integration (Ask Vyapaar Sahayak)

Set one of these environment variables (via `.env` or your shell) to enable a real LLM for the chat page:

```
GEMINI_API_KEY=your_key_here
# or
OPENAI_API_KEY=your_key_here
# or
OPENROUTER_API_KEY=your_key_here
```

If neither is set, or the API call fails for any reason (no internet, invalid key, rate limit, model
retired), the app automatically and silently falls back to **Smart Demo Mode** with a friendly
on-screen note — it never shows a raw error or crashes. 

## 9. Limitations & Disclaimer

Vyapaar Sahayak AI is a hackathon prototype using simulated and self-reported data.

- It is **not** a lender, financial advisor, credit bureau, or government portal.
- The **Business Health Indicator** is an illustrative prototype score, explicitly **not** a credit score.
- Scheme cards are always labelled **"Potentially relevant — verify eligibility"** — the app never
  declares automatic eligibility, and always links to the official government source.
- Hyper-local insights combine live weather with a small curated sample dataset for this prototype;
  the curated portion is clearly labelled and is **not** live, verified market data. The "AI Business
  Analysis" block is rule-based and explainable, not a market forecast.
- The Business Scenario Simulator recalculates the same transparent formulas used elsewhere in the app;
  it does not predict real-world outcomes and gives no guarantees.
- No guaranteed profits, loan approvals, or regulated financial/legal/tax advice are given anywhere
  in the app.

## 10. Future Roadmap

- Multi-profile support (multiple businesses / users) with authentication
- A real market-data API behind the hyper-local engine (same interface, swappable backend)
- SMS/WhatsApp-based interface for owners without smartphones
- Multi-language UI (Hindi/Punjabi content, not just a saved language preference)
- Bank/UPI statement import for automatic snapshot updates instead of manual entry
- Real demand forecasting model to replace the moving-average estimate in Inventory Insights
## AI architecture (hybrid and explainable)

Vyapaar Sahayak is intentionally **hybrid AI**, rather than an LLM-only chatbot:

- **Random Forest demand model** — forecasts next-month product demand from the shop's own monthly sales history when enough history exists.
- **Random Forest hyper-local opportunity model** — estimates opportunity probability from live weather, local-signal types, inventory coverage, margins, cash coverage, receivables and EMI burden.
- **Random Forest business-risk model** — provides a separate learned risk estimate alongside the deterministic Business Health Indicator.
- **Deterministic financial engine** — remains the safety/financial guardrail for ratios, working capital and EMI calculations; it does not pretend a statistical model is a lender.
- **LLM layer** — Gemma/Gemini/OpenAI is optional and explains, prioritises and personalises the structured outputs from the financial + ML engines. Smart Demo Mode remains available if no LLM API is configured.

### Model-training note

The current hackathon prototype trains its ML models from a **transparent, deterministic scenario dataset generated inside the application**. This makes the prototype reproducible and avoids inventing access to private rural-business data. For production, the next step is to retrain the same models on anonymised historical outcomes such as monthly demand, realised sales, inventory stock-outs and opportunity conversion.

The UI labels this explicitly so the project does not overclaim model accuracy or real-world predictive certainty.

## AI + Hyper-local upgrade (September 2026)

Vyapaar Sahayak now uses a hybrid ML architecture:

- **Contextual demand model:** Random Forest demand forecasting combines recent sales history with month/season, rainfall, festival/crop signals and nearby commercial activity when available.
- **Hyper-local opportunity model:** Random Forest opportunity scoring uses live weather, live 5 km OpenStreetMap activity, regional signals, inventory and financial context.
- **AI → inventory actions:** the opportunity engine compares ML demand forecasts with each product's actual stock and estimates the cost of a potential stock gap.
- **Explainable evidence:** every ML opportunity exposes the model inputs and the inventory action exposes the reasons behind the recommendation.
- **Live local data:** Open-Meteo provides weather/geocoding and OpenStreetMap/Overpass provides nearby mapped commercial/community context. If either live source is unavailable, the app falls back safely to curated signals.

### Important model limitation

The bundled ML models are **prototype models trained on transparent synthetic/scenario data**, not on a proprietary dataset of real rural businesses. Their purpose is to demonstrate the end-to-end architecture. A production deployment should retrain and validate them on consented, anonymised historical business outcomes and measure prediction error on held-out data.

### Architecture principle

**ML predicts. Deterministic financial rules protect. The LLM explains.**

This prevents the language model from inventing financial calculations while still providing natural-language advice.
