# Autonomous Paper Trading Bot

A learning-focused Streamlit application that follows real US market data while autonomously managing a **US$1,000 simulated portfolio**.

## Safety boundary

This repository contains a read-only Alpaca market-data client and an internal paper ledger. It contains **no brokerage trading client and no order-submission endpoint**. All positions, fills, profits and losses are simulated.

## Features

- Live Alpaca prices, market clock and financial news
- Autonomous 15-minute decision cycles during regular US market hours
- Fractional paper positions and US$1,000 starting capital
- Live snapshot pricing plus momentum, trend, volume, volatility, RSI and news research
- Broad liquid universe spanning index, sector and large-cap opportunities
- SPY-relative strength, market-breadth and risk-regime analysis
- Bot-versus-SPY benchmark, excess-return and US$1 million goal tracking
- Simulated bid/ask slippage
- Fixed exposure, position, stop-loss and profit-target controls
- Volatility-aware sizing capped at approximately 1% portfolio risk per new trade
- 12% portfolio drawdown circuit breaker for new entries
- Persistent JSON/CSV portfolio, trade, decision and equity history
- Daily per-stock allocation history with quantity, dollar value, weight and P/L
- Conservative strategy-entry calibration after sufficient completed trades
- Streamlit dashboard with holdings, allocation, equity curve and reports
- GitHub Actions scheduler that continues while the dashboard is closed

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ALPACA_API_KEY="your-market-data-key"
export ALPACA_API_SECRET="your-market-data-secret"
python scripts/run_cycle.py
streamlit run app.py
```

Do not commit credentials. The connected ChatGPT Alpaca app does not transfer its credentials into this separate application.

## GitHub setup

Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`

The included workflow runs every 15 minutes across the US trading window. It checks Alpaca's official market clock before creating paper fills and commits only the small simulation ledger, research snapshot and report files.

## Performance objective

The bot is designed to **aim** for better risk-managed returns than a US$1,000 SPY buy-and-hold benchmark. The dashboard reports excess return directly, so performance cannot be judged only by whether the dollar balance rose.

The US$1 million figure is a long-term simulation objective (a 1,000x increase), not a forecast or guarantee. It never overrides the fixed position, exposure, stop-loss or real-order prohibitions. Strategy calibration may adjust entry selectivity only after enough completed paper trades; it cannot relax the safety boundaries.

## Streamlit Community Cloud

1. Create the repository and push this project.
2. In Streamlit Community Cloud, select `app.py` as the entry point.
3. No credentials are required merely to view the committed dashboard results.
4. Configure Alpaca credentials only as GitHub Actions secrets for autonomous updates.

## Learning design

The bot may adjust only its entry selectivity after at least 12 completed paper trades. Position size, maximum exposure, stop loss and other risk boundaries are fixed in code and cannot be autonomously loosened.

## Disclaimer

Educational simulation only. Paper performance can differ substantially from achievable live results and is not financial advice.
