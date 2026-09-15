from __future__ import annotations

import os
from dataclasses import dataclass, field


DEFAULT_UNIVERSE = (
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
    "GOOGL", "META", "AVGO", "JPM", "XOM", "UNH", "COST",
)


@dataclass(frozen=True)
class Settings:
    starting_cash: float = 1_000.0
    max_position_pct: float = 0.20
    max_invested_pct: float = 0.80
    max_positions: int = 5
    minimum_order_usd: float = 20.0
    simulated_slippage_bps: float = 5.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    max_holding_days: int = 20
    universe: tuple[str, ...] = field(default_factory=lambda: DEFAULT_UNIVERSE)
    data_dir: str = "data"
    report_dir: str = "reports"
    alpaca_key: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    alpaca_secret: str = field(default_factory=lambda: os.getenv("ALPACA_API_SECRET", ""))
    alpaca_feed: str = field(default_factory=lambda: os.getenv("ALPACA_DATA_FEED", "iex"))

    @property
    def has_market_credentials(self) -> bool:
        return bool(self.alpaca_key and self.alpaca_secret)


SETTINGS = Settings()
