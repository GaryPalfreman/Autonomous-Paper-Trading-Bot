from __future__ import annotations

import math
import re
from collections import defaultdict

import pandas as pd

from .models import Signal


POSITIVE_WORDS = {
    "beat", "beats", "growth", "upgrade", "surge", "record", "profit", "strong",
    "approval", "partnership", "launch", "wins", "expands", "outperform",
}
NEGATIVE_WORDS = {
    "miss", "misses", "downgrade", "loss", "lawsuit", "recall", "cuts", "weak",
    "investigation", "decline", "warning", "fraud", "breach", "underperform",
}


def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gains = delta.clip(lower=0).rolling(period).mean()
    losses = (-delta.clip(upper=0)).rolling(period).mean()
    denominator = losses.iloc[-1]
    if pd.isna(denominator) or denominator == 0:
        return 100.0 if gains.iloc[-1] > 0 else 50.0
    rs = gains.iloc[-1] / denominator
    return float(100 - 100 / (1 + rs))


def news_scores(news: list[dict]) -> dict[str, float]:
    totals: dict[str, list[float]] = defaultdict(list)
    for item in news:
        text = f"{item.get('headline', '')} {item.get('summary', '')}".lower()
        tokens = set(re.findall(r"[a-z]+", text))
        raw = len(tokens & POSITIVE_WORDS) - len(tokens & NEGATIVE_WORDS)
        normalized = max(-1.0, min(1.0, raw / 3.0))
        for symbol in item.get("symbols", []):
            totals[symbol].append(normalized)
    return {symbol: sum(values) / len(values) for symbol, values in totals.items() if values}


def build_signal(symbol: str, frame: pd.DataFrame, current_price: float, news_score: float = 0.0) -> Signal | None:
    if frame.empty or len(frame) < 25 or current_price <= 0:
        return None
    close = frame["close"].astype(float)
    return_5 = current_price / float(close.iloc[-6]) - 1
    return_20 = current_price / float(close.iloc[-21]) - 1
    daily_returns = close.pct_change().dropna().tail(20)
    volatility = float(daily_returns.std() * math.sqrt(252)) if len(daily_returns) else 0.0
    current_rsi = rsi(pd.concat([close, pd.Series([current_price])], ignore_index=True))

    momentum_component = max(-1.0, min(1.0, return_5 / 0.05)) * 0.30
    trend_component = max(-1.0, min(1.0, return_20 / 0.12)) * 0.35
    rsi_component = max(-1.0, min(1.0, (current_rsi - 50.0) / 30.0)) * 0.15
    news_component = news_score * 0.20
    volatility_penalty = max(0.0, volatility - 0.45) * 0.20
    score = max(-1.0, min(1.0, momentum_component + trend_component + rsi_component + news_component - volatility_penalty))

    reason = (
        f"5d {return_5:+.1%}; 20d {return_20:+.1%}; RSI {current_rsi:.0f}; "
        f"annualised volatility {volatility:.1%}; news {news_score:+.2f}"
    )
    return Signal(symbol, score, current_price, return_5, return_20, current_rsi, volatility, news_score, reason)


def rank_signals(frames: dict[str, pd.DataFrame], prices: dict[str, float], news: list[dict]) -> list[Signal]:
    sentiment = news_scores(news)
    signals = []
    for symbol, frame in frames.items():
        signal = build_signal(symbol, frame, prices.get(symbol, 0.0), sentiment.get(symbol, 0.0))
        if signal:
            signals.append(signal)
    return sorted(signals, key=lambda item: item.score, reverse=True)
