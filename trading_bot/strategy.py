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


def build_signal(
    symbol: str,
    frame: pd.DataFrame,
    current_price: float,
    news_score: float = 0.0,
    benchmark_return_20d: float = 0.0,
) -> Signal | None:
    if frame.empty or len(frame) < 25 or current_price <= 0:
        return None
    close = frame["close"].astype(float)
    return_5 = current_price / float(close.iloc[-6]) - 1
    return_20 = current_price / float(close.iloc[-21]) - 1
    daily_returns = close.pct_change().dropna().tail(20)
    volatility = float(daily_returns.std() * math.sqrt(252)) if len(daily_returns) else 0.0
    current_rsi = rsi(pd.concat([close, pd.Series([current_price])], ignore_index=True))
    relative_strength = return_20 - benchmark_return_20d
    volume_ratio = 1.0
    if "volume" in frame.columns and len(frame) >= 21:
        recent_volume = float(frame["volume"].iloc[-1])
        normal_volume = float(frame["volume"].astype(float).tail(20).mean())
        if normal_volume > 0:
            volume_ratio = recent_volume / normal_volume

    momentum_component = max(-1.0, min(1.0, return_5 / 0.05)) * 0.25
    trend_component = max(-1.0, min(1.0, return_20 / 0.12)) * 0.25
    rsi_component = max(-1.0, min(1.0, (current_rsi - 50.0) / 30.0)) * 0.10
    news_component = news_score * 0.15
    relative_strength_component = max(-1.0, min(1.0, relative_strength / 0.10)) * 0.15
    volume_component = max(-1.0, min(1.0, (volume_ratio - 1.0) / 0.75)) * 0.10
    volatility_penalty = max(0.0, volatility - 0.45) * 0.20
    score = max(-1.0, min(1.0, momentum_component + trend_component + rsi_component + news_component + relative_strength_component + volume_component - volatility_penalty))

    reason = (
        f"5d {return_5:+.1%}; 20d {return_20:+.1%}; RSI {current_rsi:.0f}; "
        f"vs SPY {relative_strength:+.1%}; RSI {current_rsi:.0f}; volume {volume_ratio:.1f}x; "
        f"volatility {volatility:.1%}; news {news_score:+.2f}"
    )
    return Signal(
        symbol, score, current_price, return_5, return_20, current_rsi,
        volatility, news_score, reason, relative_strength, volume_ratio,
    )


def rank_signals(
    frames: dict[str, pd.DataFrame],
    prices: dict[str, float],
    news: list[dict],
    benchmark_symbol: str = "SPY",
) -> list[Signal]:
    sentiment = news_scores(news)
    benchmark_return = 0.0
    benchmark = frames.get(benchmark_symbol)
    benchmark_price = prices.get(benchmark_symbol, 0.0)
    if benchmark is not None and len(benchmark) >= 21 and benchmark_price > 0:
        benchmark_return = benchmark_price / float(benchmark["close"].iloc[-21]) - 1
    signals = []
    for symbol, frame in frames.items():
        signal = build_signal(
            symbol, frame, prices.get(symbol, 0.0), sentiment.get(symbol, 0.0), benchmark_return,
        )
        if signal:
            signals.append(signal)
    return sorted(signals, key=lambda item: item.score, reverse=True)
