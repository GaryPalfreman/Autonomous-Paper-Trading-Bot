from pathlib import Path

import pandas as pd

from trading_bot.models import Signal
from trading_bot.research import build_market_research
from trading_bot.storage import Storage


def frame(start: float, step: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({
        "close": [start + i * step for i in range(60)],
        "volume": [1_000_000 + i * 1_000 for i in range(60)],
    })


def test_research_detects_risk_on_market() -> None:
    frames = {"SPY": frame(100), "AAPL": frame(80)}
    prices = {"SPY": 165.0, "AAPL": 145.0}
    signal = Signal("AAPL", 0.6, 145, 0.05, 0.1, 60, 0.2, 0.1, "test")
    result = build_market_research(
        frames, prices, [], [signal], {"is_open": True}, "iex",
    )
    assert result["regime"] == "RISK_ON"
    assert result["new_entries_allowed"] is True
    assert result["universe_size"] == 2


def test_research_blocks_new_entries_in_defensive_market() -> None:
    frames = {"SPY": frame(100), "AAPL": frame(80)}
    prices = {"SPY": 90.0, "AAPL": 70.0}
    result = build_market_research(
        frames, prices, [], [], {"is_open": True}, "iex",
    )
    assert result["regime"] == "DEFENSIVE"
    assert result["new_entries_allowed"] is False


def test_benchmark_tracks_equivalent_starting_capital(tmp_path: Path) -> None:
    storage = Storage(str(tmp_path / "data"), str(tmp_path / "reports"))
    first = storage.update_benchmark("SPY", 100.0, 1_000.0)
    second = storage.update_benchmark("SPY", 110.0, 1_000.0)
    assert first["value"] == 1_000.0
    assert second["value"] == 1_100.0
    assert round(second["return"], 6) == 0.1
    assert storage.benchmark_history_path.exists()
