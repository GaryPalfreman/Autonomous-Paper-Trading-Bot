from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import pandas as pd
import requests


class MarketDataError(RuntimeError):
    pass


class AlpacaMarketData:
    """Read-only Alpaca market-data client. It contains no trading endpoint."""

    DATA_URL = "https://data.alpaca.markets"
    CLOCK_URL = "https://paper-api.alpaca.markets/v2/clock"

    def __init__(self, key: str, secret: str, feed: str = "iex", timeout: int = 20) -> None:
        if not key or not secret:
            raise MarketDataError("ALPACA_API_KEY and ALPACA_API_SECRET are required")
        self.feed = feed
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "User-Agent": "Gary-Paper-Trading-Bot/0.1",
        })

    def _get(self, url: str, params: dict | None = None) -> dict:
        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise MarketDataError(f"Alpaca returned HTTP {response.status_code}: {response.text[:250]}")
        return response.json()

    def clock(self) -> dict:
        return self._get(self.CLOCK_URL)

    def snapshots(self, symbols: Iterable[str]) -> dict[str, dict]:
        joined = ",".join(symbols)
        payload = self._get(
            f"{self.DATA_URL}/v2/stocks/snapshots",
            {"symbols": joined, "feed": self.feed},
        )
        return payload.get("snapshots", payload)

    def daily_bars(self, symbols: Iterable[str], lookback_days: int = 120) -> dict[str, pd.DataFrame]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)
        params = {
            "symbols": ",".join(symbols),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": 10_000,
            "adjustment": "all",
            "feed": self.feed,
        }
        payload = self._get(f"{self.DATA_URL}/v2/stocks/bars", params)
        frames: dict[str, pd.DataFrame] = {}
        for symbol, bars in payload.get("bars", {}).items():
            frame = pd.DataFrame(bars)
            if not frame.empty:
                frame = frame.rename(columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
                frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
                frames[symbol] = frame.sort_values("timestamp").reset_index(drop=True)
        return frames

    def recent_news(self, symbols: Iterable[str], hours: int = 36, limit: int = 50) -> list[dict]:
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        payload = self._get(
            f"{self.DATA_URL}/v1beta1/news",
            {
                "symbols": ",".join(symbols),
                "start": start.isoformat(),
                "limit": limit,
                "sort": "desc",
                "include_content": "false",
            },
        )
        return payload.get("news", [])
