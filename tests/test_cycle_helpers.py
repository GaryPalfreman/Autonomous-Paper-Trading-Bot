from scripts.run_cycle import snapshot_price, snapshot_timestamp


def test_snapshot_uses_live_midpoint_for_normal_spread() -> None:
    snapshot = {
        "latestQuote": {"bp": 99.9, "ap": 100.1, "t": "2026-01-01T10:00:01Z"},
        "latestTrade": {"p": 99.5, "t": "2026-01-01T10:00:00Z"},
    }
    assert snapshot_price(snapshot) == 100.0
    assert snapshot_timestamp(snapshot) == "2026-01-01T10:00:01Z"


def test_snapshot_rejects_implausibly_wide_quote() -> None:
    snapshot = {
        "latestQuote": {"bp": 90.0, "ap": 110.0},
        "latestTrade": {"p": 101.0},
    }
    assert snapshot_price(snapshot) == 101.0
