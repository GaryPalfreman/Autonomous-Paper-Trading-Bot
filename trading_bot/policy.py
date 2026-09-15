from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import utc_now


@dataclass
class StrategyPolicy:
    version: int = 1
    buy_threshold: float = 0.30
    sell_threshold: float = -0.12
    updated_at: str = ""
    explanation: str = "Initial balanced momentum, trend and news policy."


def load_policy(data_dir: str = "data") -> StrategyPolicy:
    path = Path(data_dir) / "strategy_policy.json"
    if not path.exists():
        policy = StrategyPolicy(updated_at=utc_now())
        save_policy(policy, data_dir)
        return policy
    return StrategyPolicy(**json.loads(path.read_text(encoding="utf-8")))


def save_policy(policy: StrategyPolicy, data_dir: str = "data") -> None:
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "strategy_policy.json").write_text(json.dumps(asdict(policy), indent=2) + "\n", encoding="utf-8")


def calibrate_policy(data_dir: str = "data") -> StrategyPolicy:
    """Conservatively calibrate entry selectivity from completed paper trades.

    Risk limits are intentionally excluded from autonomous modification.
    """
    policy = load_policy(data_dir)
    trade_path = Path(data_dir) / "trades.csv"
    if not trade_path.exists():
        return policy
    with trade_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    exits = [row for row in rows if row.get("side") == "SELL"][-20:]
    if len(exits) < 12:
        return policy
    pnl = [float(row.get("realized_pnl") or 0) for row in exits]
    win_rate = sum(value > 0 for value in pnl) / len(pnl)
    total = sum(pnl)
    new_threshold = policy.buy_threshold
    explanation = "No calibration change; recent results remain inside the neutral range."
    if win_rate < 0.45 or total < 0:
        new_threshold = min(0.55, policy.buy_threshold + 0.03)
        explanation = f"Raised entry selectivity after {len(pnl)} exits: win rate {win_rate:.0%}, P/L ${total:+.2f}."
    elif win_rate > 0.60 and total > 0:
        new_threshold = max(0.25, policy.buy_threshold - 0.02)
        explanation = f"Slightly widened entry eligibility after {len(pnl)} exits: win rate {win_rate:.0%}, P/L ${total:+.2f}."
    if new_threshold != policy.buy_threshold:
        policy = StrategyPolicy(policy.version + 1, new_threshold, policy.sell_threshold, utc_now(), explanation)
        save_policy(policy, data_dir)
        history = Path(data_dir) / "policy_history.csv"
        exists = history.exists()
        with history.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("timestamp", "version", "buy_threshold", "sell_threshold", "explanation"))
            if not exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": policy.updated_at,
                "version": policy.version,
                "buy_threshold": policy.buy_threshold,
                "sell_threshold": policy.sell_threshold,
                "explanation": policy.explanation,
            })
    return policy
