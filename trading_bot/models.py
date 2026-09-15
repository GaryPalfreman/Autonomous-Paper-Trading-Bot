from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float
    opened_at: str
    last_price: float
    highest_price: float
    entry_reason: str

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.last_price - self.average_price) * self.quantity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Portfolio:
    starting_cash: float = 1_000.0
    cash: float = 1_000.0
    realized_pnl: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    cycle_count: int = 0

    def equity(self) -> float:
        return self.cash + sum(position.market_value for position in self.positions.values())

    def invested_value(self) -> float:
        return sum(position.market_value for position in self.positions.values())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["positions"] = {key: value.to_dict() for key, value in self.positions.items()}
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Portfolio":
        positions = {
            symbol: Position(**value)
            for symbol, value in payload.get("positions", {}).items()
        }
        return cls(
            starting_cash=float(payload.get("starting_cash", 1_000.0)),
            cash=float(payload.get("cash", 1_000.0)),
            realized_pnl=float(payload.get("realized_pnl", 0.0)),
            positions=positions,
            created_at=payload.get("created_at", utc_now()),
            updated_at=payload.get("updated_at", utc_now()),
            cycle_count=int(payload.get("cycle_count", 0)),
        )


@dataclass(frozen=True)
class Signal:
    symbol: str
    score: float
    price: float
    momentum_5d: float
    momentum_20d: float
    rsi_14: float
    volatility_20d: float
    news_score: float
    reason: str


@dataclass(frozen=True)
class Trade:
    timestamp: str
    side: str
    symbol: str
    quantity: float
    fill_price: float
    notional: float
    cash_after: float
    reason: str
    score: float
    realized_pnl: float = 0.0
