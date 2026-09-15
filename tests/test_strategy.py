import pandas as pd

from trading_bot.strategy import build_signal, news_scores


def test_signal_builds_from_price_history() -> None:
    frame = pd.DataFrame({"close": [100 + i for i in range(30)]})
    result = build_signal("TEST", frame, 131.0, 0.5)
    assert result is not None
    assert result.symbol == "TEST"
    assert result.score > 0


def test_news_score_is_symbol_specific() -> None:
    scores = news_scores([{"headline": "Company beats record profit", "summary": "strong growth", "symbols": ["ABC"]}])
    assert scores["ABC"] > 0
