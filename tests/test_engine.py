from pathlib import Path

from trading_bot.config import Settings
from trading_bot.engine import PaperEngine
from trading_bot.models import Portfolio, Signal
from trading_bot.policy import StrategyPolicy
from trading_bot.storage import Storage


def signal(symbol: str, score: float, price: float) -> Signal:
    return Signal(symbol, score, price, 0.03, 0.08, 58, 0.2, 0, "test signal")


def test_buy_is_fractional_and_respects_exposure(tmp_path: Path) -> None:
    settings = Settings(data_dir=str(tmp_path / "data"), report_dir=str(tmp_path / "reports"))
    storage = Storage(settings.data_dir, settings.report_dir)
    portfolio = Portfolio(starting_cash=1000, cash=1000)
    engine = PaperEngine(settings, storage, StrategyPolicy())
    trades = engine.process(portfolio, [signal("SPY", 0.6, 500)])
    assert len(trades) == 1
    assert trades[0].side == "BUY"
    assert 0 < portfolio.positions["SPY"].quantity < 1
    assert round(portfolio.cash, 2) == 800.00


def test_stop_loss_closes_position(tmp_path: Path) -> None:
    settings = Settings(data_dir=str(tmp_path / "data"), report_dir=str(tmp_path / "reports"))
    storage = Storage(settings.data_dir, settings.report_dir)
    portfolio = Portfolio(starting_cash=1000, cash=1000)
    engine = PaperEngine(settings, storage, StrategyPolicy())
    engine.process(portfolio, [signal("AAPL", 0.8, 100)])
    trades = engine.process(portfolio, [signal("AAPL", 0.1, 94)])
    assert any(trade.side == "SELL" for trade in trades)
    assert "AAPL" not in portfolio.positions
    assert portfolio.realized_pnl < 0


def test_no_trade_below_threshold(tmp_path: Path) -> None:
    settings = Settings(data_dir=str(tmp_path / "data"), report_dir=str(tmp_path / "reports"))
    storage = Storage(settings.data_dir, settings.report_dir)
    portfolio = Portfolio(starting_cash=1000, cash=1000)
    trades = PaperEngine(settings, storage, StrategyPolicy()).process(portfolio, [signal("QQQ", 0.1, 400)])
    assert trades == []
    assert portfolio.cash == 1000


def test_defensive_regime_blocks_new_position(tmp_path: Path) -> None:
    settings = Settings(data_dir=str(tmp_path / "data"), report_dir=str(tmp_path / "reports"))
    storage = Storage(settings.data_dir, settings.report_dir)
    portfolio = Portfolio(starting_cash=1000, cash=1000)
    trades = PaperEngine(settings, storage, StrategyPolicy()).process(
        portfolio, [signal("NVDA", 0.9, 200)], allow_new_entries=False,
    )
    assert trades == []
    assert portfolio.positions == {}
    assert "RISK_BLOCKED" in storage.decisions_path.read_text(encoding="utf-8")
