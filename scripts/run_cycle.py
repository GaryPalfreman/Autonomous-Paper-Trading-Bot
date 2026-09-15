from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trading_bot.config import SETTINGS  # noqa: E402
from trading_bot.engine import PaperEngine, make_report  # noqa: E402
from trading_bot.market_data import AlpacaMarketData  # noqa: E402
from trading_bot.policy import calibrate_policy, load_policy  # noqa: E402
from trading_bot.research import build_market_research  # noqa: E402
from trading_bot.storage import Storage  # noqa: E402
from trading_bot.strategy import rank_signals  # noqa: E402


def snapshot_price(snapshot: dict) -> float:
    quote = snapshot.get("latestQuote") or snapshot.get("latest_quote") or {}
    trade = snapshot.get("latestTrade") or snapshot.get("latest_trade") or {}
    minute = snapshot.get("minuteBar") or snapshot.get("minute_bar") or {}
    ask = quote.get("ap") or quote.get("ask_price")
    bid = quote.get("bp") or quote.get("bid_price")
    if ask and bid:
        ask_value, bid_value = float(ask), float(bid)
        midpoint = (ask_value + bid_value) / 2
        # Reject stale or crossed quotes; a human trader would not value a
        # position from an implausibly wide spread.
        if ask_value >= bid_value and (ask_value - bid_value) / midpoint <= 0.02:
            return midpoint
    return float(trade.get("p") or trade.get("price") or minute.get("c") or minute.get("close") or 0)


def snapshot_timestamp(snapshot: dict) -> str:
    candidates = []
    for key in ("latestTrade", "latest_trade", "latestQuote", "latest_quote", "minuteBar", "minute_bar"):
        value = snapshot.get(key) or {}
        timestamp = value.get("t") or value.get("timestamp")
        if timestamp:
            candidates.append(str(timestamp))
    return max(candidates, default="")


def main() -> int:
    storage = Storage(SETTINGS.data_dir, SETTINGS.report_dir)
    portfolio = storage.load_portfolio(SETTINGS.starting_cash)
    client = AlpacaMarketData(SETTINGS.alpaca_key, SETTINGS.alpaca_secret, SETTINGS.alpaca_feed)
    clock = client.clock()
    snapshots = client.snapshots(SETTINGS.universe)
    prices = {symbol: snapshot_price(value) for symbol, value in snapshots.items()}
    latest_market_timestamp = max((snapshot_timestamp(value) for value in snapshots.values()), default="")
    bars = client.daily_bars(SETTINGS.universe)
    news = client.recent_news(SETTINGS.universe)
    signals = rank_signals(bars, prices, news, SETTINGS.benchmark_symbol)
    research = build_market_research(
        bars, prices, news, signals, clock, SETTINGS.alpaca_feed, SETTINGS.benchmark_symbol,
        latest_market_timestamp,
    )
    storage.write_research(research)
    benchmark = storage.update_benchmark(
        SETTINGS.benchmark_symbol,
        prices.get(SETTINGS.benchmark_symbol, 0.0),
        portfolio.starting_cash,
    )

    # Revalue while closed, but do not create simulated fills outside regular hours.
    for symbol, position in portfolio.positions.items():
        if prices.get(symbol):
            position.last_price = prices[symbol]
            position.highest_price = max(position.highest_price, prices[symbol])
    policy = load_policy(SETTINGS.data_dir)
    trades = (
        PaperEngine(SETTINGS, storage, policy).process(
            portfolio, signals, allow_new_entries=bool(research["new_entries_allowed"]),
        )
        if clock.get("is_open") else []
    )
    if not clock.get("is_open"):
        storage.save_portfolio(portfolio)
        storage.append_equity(portfolio)
    storage.append_positions_snapshot(portfolio)
    report = make_report(
        portfolio, signals, trades, bool(clock.get("is_open")), benchmark, research, SETTINGS.portfolio_goal,
    )
    storage.write_report(report)
    calibrate_policy(SETTINGS.data_dir)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
