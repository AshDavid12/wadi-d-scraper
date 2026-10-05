from __future__ import annotations

from datetime import datetime, timezone

from wadi_scraper.diff import UrlRow, detect_bulk_lastmod_stamp, diff_inventory


def _row(url: str, lastmod: datetime | None = None) -> UrlRow:
    return UrlRow(url=url, page_type="page", lastmod=lastmod)


def test_baseline_when_no_previous():
    current = {"https://example.com/a": _row("https://example.com/a")}
    diff = diff_inventory(None, current)
    assert diff.baseline is True
    assert diff.added == []
    assert diff.removed == []


def test_added_and_removed():
    prev = {
        "https://example.com/a": _row("https://example.com/a"),
        "https://example.com/b": _row("https://example.com/b"),
    }
    curr = {
        "https://example.com/a": _row("https://example.com/a"),
        "https://example.com/c": _row("https://example.com/c"),
    }
    diff = diff_inventory(prev, curr)
    assert diff.baseline is False
    assert diff.added == ["https://example.com/c"]
    assert diff.removed == ["https://example.com/b"]


def test_bulk_lastmod_stamp():
    ts = datetime(2026, 1, 2, tzinfo=timezone.utc)
    prev = {f"https://example.com/p{i}": _row(f"https://example.com/p{i}", datetime(2025, 1, 1, tzinfo=timezone.utc)) for i in range(100)}
    curr = {}
    for i in range(100):
        curr[f"https://example.com/p{i}"] = _row(f"https://example.com/p{i}", ts)
    stamp = detect_bulk_lastmod_stamp(prev, curr)
    assert stamp is not None
    assert stamp.url_count >= 80
