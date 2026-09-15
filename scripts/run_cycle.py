from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trading_bot.config import SETTINGS  # noqa: E402
from trading_bot.engine import PaperEngine, make_report  # noqa: E402
from trading_bot.market_data import AlpacaMarketData  # noqa: E402
from trading_bot.policy import calibrate_policy, load_policy  # noqa: E402
from trading_bot.storage import Storage  # noqa: E402
from trading_bot.strategy import rank_signals  # noqa: E402


def snapshot_price(snapshot: dict) -> float:
    quote = snapshot.get("latestQuote") or snapshot.get("latest_quote") or {}
    trade = snapshot.get("latestTrade") or snapshot.get("latest_trade") or {}
    minute = snapshot.get("minuteBar") or snapshot.get("minute_bar") or {}
    ask = quote.get("ap") or quote.get("ask_price")
    bid = quote.get("bp") or quote.get("bid_price")
    if ask and bid:
        return (float(ask) + float(bid)) / 2
    return float(trade.get("p") or trade.get("price") or minute.get("c") or minute.get("close") or 0)


def main() -> int:
    storage = Storage(SETTINGS.data_dir, SETTINGS.report_dir)
    portfolio = storage.load_portfolio(SETTINGS.starting_cash)
    client = AlpacaMarketData(SETTINGS.alpaca_key, SETTINGS.alpaca_secret, SETTINGS.alpaca_feed)
    clock = client.clock()
    snapshots = client.snapshots(SETTINGS.universe)
    prices = {symbol: snapshot_price(value) for symbol, value in snapshots.items()}
    bars = client.daily_bars(SETTINGS.universe)
    news = client.recent_news(SETTINGS.universe)
    signals = rank_signals(bars, prices, news)

    # Revalue while closed, but do not create simulated fills outside regular hours.
    for symbol, position in portfolio.positions.items():
        if prices.get(symbol):
            position.last_price = prices[symbol]
            position.highest_price = max(position.highest_price, prices[symbol])
    policy = load_policy(SETTINGS.data_dir)
    trades = PaperEngine(SETTINGS, storage, policy).process(portfolio, signals) if clock.get("is_open") else []
    if not clock.get("is_open"):
        storage.save_portfolio(portfolio)
        storage.append_equity(portfolio)
    report = make_report(portfolio, signals, trades, bool(clock.get("is_open")))
    storage.write_report(report)
    calibrate_policy(SETTINGS.data_dir)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
