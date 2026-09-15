from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from .models import Portfolio, Trade, utc_now


TRADE_FIELDS = (
    "timestamp", "side", "symbol", "quantity", "fill_price", "notional",
    "cash_after", "reason", "score", "realized_pnl",
)


class Storage:
    def __init__(self, data_dir: str = "data", report_dir: str = "reports") -> None:
        self.data_dir = Path(data_dir)
        self.report_dir = Path(report_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.portfolio_path = self.data_dir / "portfolio.json"
        self.trades_path = self.data_dir / "trades.csv"
        self.equity_path = self.data_dir / "equity_history.csv"
        self.decisions_path = self.data_dir / "decisions.csv"
        self.benchmark_path = self.data_dir / "benchmark.json"
        self.research_path = self.data_dir / "research.json"
        self.benchmark_history_path = self.data_dir / "benchmark_history.csv"
        self.positions_history_path = self.data_dir / "positions_history.csv"

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_name = handle.name
        os.replace(temp_name, path)

    def load_portfolio(self, starting_cash: float = 1_000.0) -> Portfolio:
        if not self.portfolio_path.exists():
            portfolio = Portfolio(starting_cash=starting_cash, cash=starting_cash)
            self.save_portfolio(portfolio)
            return portfolio
        return Portfolio.from_dict(json.loads(self.portfolio_path.read_text(encoding="utf-8")))

    def save_portfolio(self, portfolio: Portfolio) -> None:
        portfolio.updated_at = utc_now()
        self._atomic_json(self.portfolio_path, portfolio.to_dict())

    @staticmethod
    def _append_csv(path: Path, fields: Iterable[str], row: dict) -> None:
        exists = path.exists() and path.stat().st_size > 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields))
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    def append_trade(self, trade: Trade) -> None:
        self._append_csv(self.trades_path, TRADE_FIELDS, trade.__dict__)

    def append_equity(self, portfolio: Portfolio) -> None:
        self._append_csv(
            self.equity_path,
            ("timestamp", "equity", "cash", "invested", "realized_pnl", "positions"),
            {
                "timestamp": utc_now(),
                "equity": round(portfolio.equity(), 4),
                "cash": round(portfolio.cash, 4),
                "invested": round(portfolio.invested_value(), 4),
                "realized_pnl": round(portfolio.realized_pnl, 4),
                "positions": len(portfolio.positions),
            },
        )

    def append_decision(self, row: dict) -> None:
        fields = ("timestamp", "symbol", "action", "score", "price", "reason")
        self._append_csv(self.decisions_path, fields, row)

    def update_benchmark(self, symbol: str, price: float, starting_cash: float) -> dict:
        if price <= 0:
            return {}
        if self.benchmark_path.exists():
            payload = json.loads(self.benchmark_path.read_text(encoding="utf-8"))
        else:
            payload = {
                "symbol": symbol,
                "starting_cash": starting_cash,
                "start_price": price,
                "started_at": utc_now(),
            }
        payload["latest_price"] = price
        payload["updated_at"] = utc_now()
        payload["value"] = starting_cash * price / float(payload["start_price"])
        payload["return"] = payload["value"] / starting_cash - 1
        self._atomic_json(self.benchmark_path, payload)
        self._append_csv(
            self.benchmark_history_path,
            ("timestamp", "symbol", "price", "value", "return"),
            {
                "timestamp": payload["updated_at"],
                "symbol": symbol,
                "price": round(price, 6),
                "value": round(payload["value"], 4),
                "return": round(payload["return"], 8),
            },
        )
        return payload

    def write_research(self, payload: dict) -> None:
        self._atomic_json(self.research_path, payload)

    def append_positions_snapshot(self, portfolio: Portfolio) -> None:
        timestamp = utc_now()
        equity = portfolio.equity()
        fields = (
            "timestamp", "date", "symbol", "quantity", "average_entry", "latest_price",
            "market_value", "portfolio_weight", "unrealized_pnl",
        )
        rows = []
        for position in portfolio.positions.values():
            rows.append({
                "timestamp": timestamp,
                "date": timestamp[:10],
                "symbol": position.symbol,
                "quantity": round(position.quantity, 8),
                "average_entry": round(position.average_price, 6),
                "latest_price": round(position.last_price, 6),
                "market_value": round(position.market_value, 4),
                "portfolio_weight": round(position.market_value / equity, 8) if equity else 0,
                "unrealized_pnl": round(position.unrealized_pnl, 4),
            })
        rows.append({
            "timestamp": timestamp,
            "date": timestamp[:10],
            "symbol": "CASH",
            "quantity": 1,
            "average_entry": 1,
            "latest_price": 1,
            "market_value": round(portfolio.cash, 4),
            "portfolio_weight": round(portfolio.cash / equity, 8) if equity else 0,
            "unrealized_pnl": 0,
        })
        for row in rows:
            self._append_csv(self.positions_history_path, fields, row)

    def write_report(self, content: str) -> None:
        (self.report_dir / "latest.md").write_text(content, encoding="utf-8")
