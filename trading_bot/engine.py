from __future__ import annotations

from datetime import datetime, timezone

from .config import Settings
from .models import Portfolio, Position, Signal, Trade, utc_now
from .policy import StrategyPolicy
from .storage import Storage


class PaperEngine:
    def __init__(self, settings: Settings, storage: Storage, policy: StrategyPolicy | None = None) -> None:
        self.settings = settings
        self.storage = storage
        self.policy = policy or StrategyPolicy()

    def _fill_price(self, price: float, side: str) -> float:
        slip = self.settings.simulated_slippage_bps / 10_000
        return price * (1 + slip if side == "BUY" else 1 - slip)

    def _sell(self, portfolio: Portfolio, position: Position, price: float, reason: str, score: float) -> Trade:
        fill = self._fill_price(price, "SELL")
        notional = position.quantity * fill
        pnl = (fill - position.average_price) * position.quantity
        portfolio.cash += notional
        portfolio.realized_pnl += pnl
        del portfolio.positions[position.symbol]
        trade = Trade(utc_now(), "SELL", position.symbol, position.quantity, fill, notional, portfolio.cash, reason, score, pnl)
        self.storage.append_trade(trade)
        return trade

    def _buy(self, portfolio: Portfolio, signal: Signal) -> Trade | None:
        equity = portfolio.equity()
        target = min(equity * self.settings.max_position_pct, portfolio.cash - equity * (1 - self.settings.max_invested_pct))
        if target < self.settings.minimum_order_usd:
            return None
        fill = self._fill_price(signal.price, "BUY")
        quantity = target / fill
        portfolio.cash -= target
        portfolio.positions[signal.symbol] = Position(
            signal.symbol, quantity, fill, utc_now(), signal.price, signal.price, signal.reason,
        )
        trade = Trade(utc_now(), "BUY", signal.symbol, quantity, fill, target, portfolio.cash, signal.reason, signal.score)
        self.storage.append_trade(trade)
        return trade

    def process(self, portfolio: Portfolio, signals: list[Signal], allow_new_entries: bool = True) -> list[Trade]:
        by_symbol = {signal.symbol: signal for signal in signals}
        trades: list[Trade] = []

        for symbol in list(portfolio.positions):
            position = portfolio.positions[symbol]
            signal = by_symbol.get(symbol)
            if not signal:
                continue
            position.last_price = signal.price
            position.highest_price = max(position.highest_price, signal.price)
            opened = datetime.fromisoformat(position.opened_at.replace("Z", "+00:00"))
            held_days = (datetime.now(timezone.utc) - opened).days
            return_pct = signal.price / position.average_price - 1
            reason = None
            if return_pct <= -self.settings.stop_loss_pct:
                reason = f"Risk exit: stop loss reached at {return_pct:+.1%}"
            elif return_pct >= self.settings.take_profit_pct:
                reason = f"Profit exit: target reached at {return_pct:+.1%}"
            elif held_days >= self.settings.max_holding_days:
                reason = f"Time exit after {held_days} days"
            elif signal.score <= self.policy.sell_threshold:
                reason = f"Signal exit: score declined to {signal.score:+.2f}; {signal.reason}"
            if reason:
                trades.append(self._sell(portfolio, position, signal.price, reason, signal.score))

        for signal in signals:
            if not allow_new_entries:
                break
            if len(portfolio.positions) >= self.settings.max_positions:
                break
            if signal.symbol in portfolio.positions or signal.score < self.policy.buy_threshold:
                continue
            trade = self._buy(portfolio, signal)
            if trade:
                trades.append(trade)

        for signal in signals:
            default_action = "HOLD" if signal.symbol in portfolio.positions else "WATCH"
            action = next((trade.side for trade in trades if trade.symbol == signal.symbol), default_action)
            reason = signal.reason
            if not allow_new_entries and action == "WATCH" and signal.score >= self.policy.buy_threshold:
                action = "RISK_BLOCKED"
                reason = f"New entry blocked by defensive market regime; {signal.reason}"
            self.storage.append_decision({
                "timestamp": utc_now(), "symbol": signal.symbol, "action": action,
                "score": round(signal.score, 5), "price": signal.price, "reason": reason,
            })

        portfolio.cycle_count += 1
        self.storage.save_portfolio(portfolio)
        self.storage.append_equity(portfolio)
        return trades


def make_report(
    portfolio: Portfolio,
    signals: list[Signal],
    trades: list[Trade],
    market_open: bool,
    benchmark: dict | None = None,
    research: dict | None = None,
    goal: float = 1_000_000.0,
) -> str:
    equity = portfolio.equity()
    total_return = equity / portfolio.starting_cash - 1
    lines = [
        "# Autonomous Paper Portfolio — Latest Update",
        "",
        f"Generated: {utc_now()}",
        f"Market open: {'Yes' if market_open else 'No'}",
        f"Portfolio value: **${equity:,.2f}** ({total_return:+.2%})",
        f"Cash: **${portfolio.cash:,.2f}**",
        f"Invested: **${portfolio.invested_value():,.2f}**",
        f"Realised P/L: **${portfolio.realized_pnl:+,.2f}**",
    ]
    if benchmark:
        benchmark_return = float(benchmark.get("return", 0.0))
        lines += [
            f"SPY benchmark: **${float(benchmark.get('value', portfolio.starting_cash)):,.2f}** ({benchmark_return:+.2%})",
            f"Excess return vs SPY: **{total_return - benchmark_return:+.2%}**",
        ]
    lines += [
        f"Long-term simulated goal: **${goal:,.0f}** ({equity / goal:.4%} complete; {goal / max(equity, 0.01):,.1f}x remaining)",
        "",
        "## Market research",
    ]
    if research:
        lines += [
            f"- Regime: **{research.get('regime', 'UNKNOWN')}** (breadth above 20-day average: {float(research.get('breadth_above_20d_average', 0)):.0%})",
            f"- Source: {research.get('data_source', 'market data')} / {research.get('data_feed', 'unknown')} feed; {research.get('universe_size', 0)} liquid symbols; {research.get('news_articles_reviewed', 0)} recent articles",
            f"- New entries allowed: **{'Yes' if research.get('new_entries_allowed') else 'No'}**",
        ]
    else:
        lines.append("- Research snapshot unavailable.")
    lines += [
        "",
        "## Positions",
    ]
    if portfolio.positions:
        lines += ["| Symbol | Quantity | Average | Latest | Value | Unrealised P/L |", "|---|---:|---:|---:|---:|---:|"]
        for position in portfolio.positions.values():
            lines.append(
                f"| {position.symbol} | {position.quantity:.5f} | ${position.average_price:.2f} | "
                f"${position.last_price:.2f} | ${position.market_value:.2f} | ${position.unrealized_pnl:+.2f} |"
            )
    else:
        lines.append("No open positions.")
    lines += ["", "## Trades this cycle"]
    if trades:
        for trade in trades:
            lines.append(f"- **{trade.side} {trade.symbol}** — ${trade.notional:.2f} at ${trade.fill_price:.2f}: {trade.reason}")
    else:
        lines.append("- No trades. Holding cash or existing positions was the highest-ranked decision.")
    lines += ["", "## Highest-ranked signals"]
    for signal in signals[:5]:
        lines.append(f"- **{signal.symbol} {signal.score:+.2f}** — {signal.reason}")
    lines += ["", "> Educational simulation only. It cannot submit real brokerage orders.", ""]
    return "\n".join(lines)
