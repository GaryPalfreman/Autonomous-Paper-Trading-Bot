from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from trading_bot.config import SETTINGS
from trading_bot.models import Portfolio
from trading_bot.policy import load_policy


st.set_page_config(page_title="Autonomous Paper Trader", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
      .stApp {background: radial-gradient(circle at 10% 0%, #152436 0, #08111c 42%, #050a11 100%);}
      [data-testid="stMetric"] {background:#0d1a28;border:1px solid #20384f;padding:16px;border-radius:14px;}
      .hero {padding:24px 28px;border:1px solid #24445f;border-radius:18px;background:linear-gradient(135deg,#102537,#0b1723);margin-bottom:20px;}
      .hero h1 {margin:0;color:#e8f4ff;font-size:2rem}.hero p {margin:.5rem 0 0;color:#93abc0}
      .safe {color:#68e0aa;font-weight:700}.muted {color:#8da2b5}
    </style>
    """,
    unsafe_allow_html=True,
)

DATA = Path("data")
REPORTS = Path("reports")


def read_csv(name: str) -> pd.DataFrame:
    path = DATA / name
    return pd.read_csv(path) if path.exists() and path.stat().st_size else pd.DataFrame()


def read_json(name: str) -> dict:
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@st.cache_data(ttl=30)
def load_data() -> tuple[Portfolio, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str, dict, dict]:
    path = DATA / "portfolio.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"starting_cash": 1000, "cash": 1000}
    portfolio = Portfolio.from_dict(payload)
    report_path = REPORTS / "latest.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else "No cycle report has been generated yet."
    return (
        portfolio,
        read_csv("equity_history.csv"),
        read_csv("benchmark_history.csv"),
        read_csv("trades.csv"),
        read_csv("decisions.csv"),
        report,
        read_json("benchmark.json"),
        read_json("research.json"),
    )


portfolio, equity, benchmark_history, trades, decisions, report, benchmark, research = load_data()
policy = load_policy(SETTINGS.data_dir)
total_return = portfolio.equity() / portfolio.starting_cash - 1
benchmark_return = float(benchmark.get("return", 0.0))
alpha = total_return - benchmark_return

st.markdown(
    '<div class="hero"><h1>Autonomous Paper Trader</h1>'
    '<p>Real US market data · US$1,000 virtual capital · autonomous simulation · '
    '<span class="safe">no real-order capability</span></p></div>',
    unsafe_allow_html=True,
)

cols = st.columns(6)
cols[0].metric("Portfolio value", f"${portfolio.equity():,.2f}", f"{total_return:+.2%}")
cols[1].metric("vs SPY", f"{alpha:+.2%}", f"SPY {benchmark_return:+.2%}")
cols[2].metric("Available cash", f"${portfolio.cash:,.2f}")
cols[3].metric("Invested", f"${portfolio.invested_value():,.2f}")
cols[4].metric("Realised P/L", f"${portfolio.realized_pnl:+,.2f}")
cols[5].metric("Open positions", len(portfolio.positions))

overview, research_tab, activity, intelligence, system = st.tabs(
    ["Portfolio", "Market research", "Trade journal", "Decision intelligence", "System"]
)

with overview:
    left, right = st.columns([1.7, 1])
    with left:
        st.subheader("Equity curve")
        if not equity.empty:
            equity["timestamp"] = pd.to_datetime(equity["timestamp"], utc=True)
            portfolio_curve = equity[["timestamp", "equity"]].rename(columns={"equity": "Value"})
            portfolio_curve["Series"] = "Bot portfolio"
            curves = [portfolio_curve]
            if not benchmark_history.empty:
                benchmark_history["timestamp"] = pd.to_datetime(benchmark_history["timestamp"], utc=True)
                spy_curve = benchmark_history[["timestamp", "value"]].rename(columns={"value": "Value"})
                spy_curve["Series"] = "SPY benchmark"
                curves.append(spy_curve)
            figure = px.line(pd.concat(curves), x="timestamp", y="Value", color="Series", markers=True)
            figure.update_layout(template="plotly_dark", height=360, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="US dollars", xaxis_title="")
            st.plotly_chart(figure, width="stretch")
        else:
            st.info("The equity curve appears after the first automated market cycle.")
    with right:
        st.subheader("Allocation")
        allocation = [{"Asset": symbol, "Value": p.market_value} for symbol, p in portfolio.positions.items()]
        allocation.append({"Asset": "Cash", "Value": portfolio.cash})
        fig = px.pie(pd.DataFrame(allocation), names="Asset", values="Value", hole=0.62)
        fig.update_layout(template="plotly_dark", height=360, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Current holdings")
    holdings = []
    for p in portfolio.positions.values():
        holdings.append({
            "Symbol": p.symbol, "Quantity": p.quantity, "Average entry": p.average_price,
            "Latest": p.last_price, "Market value": p.market_value, "Unrealised P/L": p.unrealized_pnl,
            "Opened": p.opened_at, "Entry reasoning": p.entry_reason,
        })
    if holdings:
        st.dataframe(pd.DataFrame(holdings), width="stretch", hide_index=True)
    else:
        st.info("The bot is currently holding 100% cash.")

    st.subheader("US$1 million simulation objective")
    progress = min(portfolio.equity() / SETTINGS.portfolio_goal, 1.0)
    st.progress(progress)
    st.caption(
        f"${portfolio.equity():,.2f} of ${SETTINGS.portfolio_goal:,.0f} · "
        f"{progress:.4%} complete · {SETTINGS.portfolio_goal / max(portfolio.equity(), 0.01):,.1f}x remaining. "
        "The objective does not override the fixed risk limits."
    )

with research_tab:
    st.subheader("Current market regime")
    if not research:
        st.info("Research appears after the next autonomous market-data cycle.")
    else:
        rcols = st.columns(4)
        rcols[0].metric("Regime", research.get("regime", "Unknown"))
        rcols[1].metric("Market breadth", f"{float(research.get('breadth_above_20d_average', 0)):.0%}")
        rcols[2].metric("Symbols researched", int(research.get("universe_size", 0)))
        rcols[3].metric("News reviewed", int(research.get("news_articles_reviewed", 0)))
        st.caption(
            f"Live source: {research.get('data_source', 'Unknown')} ({research.get('data_feed', 'unknown')} feed) · "
            f"Latest market event {research.get('latest_market_timestamp') or 'unknown'} · "
            f"Research generated {research.get('generated_at', 'unknown')} · "
            f"Market {'open' if research.get('market_is_open') else 'closed'}"
        )
        candidates = pd.DataFrame(research.get("top_candidates", []))
        st.subheader("Ranked opportunities")
        if candidates.empty:
            st.info("No eligible candidates were produced.")
        else:
            st.dataframe(candidates, width="stretch", hide_index=True)
        headlines = pd.DataFrame(research.get("recent_news", []))
        st.subheader("Recent market news reviewed")
        if headlines.empty:
            st.info("No recent news was returned for the research universe.")
        else:
            st.dataframe(headlines, width="stretch", hide_index=True)
        if not research.get("new_entries_allowed", False):
            st.warning("Defensive regime: new entries are blocked while existing positions remain protected by exit rules.")

with activity:
    st.subheader("Executed paper trades")
    st.caption("Every fill includes simulated slippage. These records never reach a brokerage order endpoint.")
    if trades.empty:
        st.info("No paper trades have been placed yet.")
    else:
        st.dataframe(trades.sort_values("timestamp", ascending=False), width="stretch", hide_index=True)

with intelligence:
    st.subheader("Latest autonomous decisions")
    if decisions.empty:
        st.info("Decision records appear after the first market cycle.")
    else:
        latest = decisions.sort_values("timestamp", ascending=False).head(50)
        st.dataframe(latest, width="stretch", hide_index=True)
    st.subheader("Latest report")
    st.markdown(report.replace("$", r"\$"))

with system:
    st.subheader("Strategy policy")
    st.json({
        "policy_version": policy.version,
        "buy_threshold": policy.buy_threshold,
        "sell_threshold": policy.sell_threshold,
        "explanation": policy.explanation,
        "last_updated": policy.updated_at,
    })
    st.subheader("Fixed safety boundaries")
    st.write({
        "starting_virtual_cash": SETTINGS.starting_cash,
        "maximum_position": f"{SETTINGS.max_position_pct:.0%}",
        "maximum_invested": f"{SETTINGS.max_invested_pct:.0%}",
        "maximum_positions": SETTINGS.max_positions,
        "stop_loss": f"{SETTINGS.stop_loss_pct:.0%}",
        "take_profit": f"{SETTINGS.take_profit_pct:.0%}",
        "simulated_slippage": f"{SETTINGS.simulated_slippage_bps:.0f} bps",
        "benchmark": SETTINGS.benchmark_symbol,
        "long_term_goal": f"${SETTINGS.portfolio_goal:,.0f}",
        "research_universe": len(SETTINGS.universe),
    })
    st.warning("Educational paper simulation only. Results do not represent achievable live performance or financial advice.")
    if not (os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_API_SECRET")):
        st.caption("Dashboard mode is active. Scheduled market cycles require Alpaca data credentials in GitHub Actions secrets.")
