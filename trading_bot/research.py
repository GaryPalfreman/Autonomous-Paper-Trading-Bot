from __future__ import annotations

from typing import Any

import pandas as pd

from .models import Signal, utc_now


def _above_average(frame: pd.DataFrame, price: float, days: int) -> bool:
    if frame.empty or len(frame) < days or price <= 0:
        return False
    return price > float(frame["close"].astype(float).tail(days).mean())


def build_market_research(
    frames: dict[str, pd.DataFrame],
    prices: dict[str, float],
    news: list[dict],
    signals: list[Signal],
    clock: dict[str, Any],
    feed: str,
    benchmark_symbol: str = "SPY",
    latest_market_timestamp: str | None = None,
) -> dict[str, Any]:
    """Create an auditable research snapshot from price, breadth and news data."""
    valid = [(symbol, frame) for symbol, frame in frames.items() if prices.get(symbol, 0) > 0]
    breadth_20d = (
        sum(_above_average(frame, prices[symbol], 20) for symbol, frame in valid) / len(valid)
        if valid else 0.0
    )
    benchmark = frames.get(benchmark_symbol)
    benchmark_price = prices.get(benchmark_symbol, 0.0)
    benchmark_above_20d = bool(benchmark is not None and _above_average(benchmark, benchmark_price, 20))
    benchmark_above_50d = bool(benchmark is not None and _above_average(benchmark, benchmark_price, 50))
    regime_score = (0.35 if benchmark_above_20d else -0.35) + (0.35 if benchmark_above_50d else -0.35)
    regime_score += (breadth_20d - 0.5) * 0.6
    if regime_score >= 0.35:
        regime = "RISK_ON"
    elif regime_score <= -0.35:
        regime = "DEFENSIVE"
    else:
        regime = "NEUTRAL"

    return {
        "generated_at": utc_now(),
        "data_source": "Alpaca Market Data",
        "data_feed": feed,
        "latest_market_timestamp": latest_market_timestamp,
        "market_is_open": bool(clock.get("is_open")),
        "next_open": clock.get("next_open"),
        "next_close": clock.get("next_close"),
        "universe_size": len(valid),
        "news_articles_reviewed": len(news),
        "benchmark_symbol": benchmark_symbol,
        "benchmark_price": round(benchmark_price, 6),
        "benchmark_above_20d_average": benchmark_above_20d,
        "benchmark_above_50d_average": benchmark_above_50d,
        "breadth_above_20d_average": round(breadth_20d, 6),
        "regime_score": round(regime_score, 6),
        "regime": regime,
        "new_entries_allowed": regime != "DEFENSIVE",
        "top_candidates": [
            {
                "symbol": signal.symbol,
                "score": round(signal.score, 6),
                "price": round(signal.price, 6),
                "relative_strength_20d": round(signal.relative_strength_20d, 6),
                "news_score": round(signal.news_score, 6),
                "reason": signal.reason,
            }
            for signal in signals[:10]
        ],
    }
