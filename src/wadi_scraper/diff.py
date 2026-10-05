from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


@dataclass
class UrlRow:
    url: str
    page_type: str
    lastmod: datetime | None


@dataclass
class BulkLastmodStamp:
    timestamp: str
    url_count: int


@dataclass
class InventoryDiff:
    baseline: bool
    days_since_previous: int | None
    previous_run_id: int | None
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added_remainder: int = 0
    removed_remainder: int = 0
    tier_c_added_count: int = 0
    tier_c_removed_count: int = 0
    bulk_lastmod_ignored: BulkLastmodStamp | None = None
    lastmod_changed_count: int = 0


LIST_CAP = 100


def _lastmod_key(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def diff_inventory(
    previous: dict[str, UrlRow] | None,
    current: dict[str, UrlRow],
    *,
    list_cap: int = LIST_CAP,
    tier_fn: Optional[Callable[[str, str], str]] = None,
) -> InventoryDiff:
    if previous is None:
        return InventoryDiff(baseline=True, days_since_previous=None, previous_run_id=None)

    prev_urls = set(previous.keys())
    curr_urls = set(current.keys())
    added_all = sorted(curr_urls - prev_urls)
    removed_all = sorted(prev_urls - curr_urls)

    def tier(url: str, source: dict[str, UrlRow]) -> str:
        if tier_fn is None:
            return "B"
        row = source.get(url)
        if not row:
            return "B"
        return tier_fn(url, row.page_type)

    from wadi_scraper.tiers import TIER_C

    added_ab = [u for u in added_all if tier(u, current) != TIER_C]
    removed_ab = [u for u in removed_all if tier(u, previous) != TIER_C]

    return InventoryDiff(
        baseline=False,
        days_since_previous=None,
        previous_run_id=None,
        added=added_ab[:list_cap],
        removed=removed_ab[:list_cap],
        added_remainder=max(0, len(added_ab) - list_cap),
        removed_remainder=max(0, len(removed_ab) - list_cap),
        tier_c_added_count=len(added_all) - len(added_ab),
        tier_c_removed_count=len(removed_all) - len(removed_ab),
        bulk_lastmod_ignored=detect_bulk_lastmod_stamp(previous, current),
        lastmod_changed_count=_count_selective_lastmod_changes(previous, current),
    )


def detect_bulk_lastmod_stamp(
    previous: dict[str, UrlRow],
    current: dict[str, UrlRow],
) -> BulkLastmodStamp | None:
    inventory_size = len(current)
    if inventory_size == 0:
        return None

    changed: list[tuple[str, str]] = []
    for url, row in current.items():
        if url not in previous:
            continue
        old = _lastmod_key(previous[url].lastmod)
        new = _lastmod_key(row.lastmod)
        if old is None or new is None or old == new:
            continue
        changed.append((url, new))

    if not changed:
        return None

    threshold = max(50, int(inventory_size * 0.10))
    if len(changed) <= threshold:
        return None

    by_ts: dict[str, int] = {}
    for _, ts in changed:
        by_ts[ts] = by_ts.get(ts, 0) + 1

    best_ts = max(by_ts, key=by_ts.get)
    best_count = by_ts[best_ts]
    if best_count / len(changed) >= 0.80:
        return BulkLastmodStamp(timestamp=best_ts, url_count=best_count)
    return None


def _count_selective_lastmod_changes(
    previous: dict[str, UrlRow],
    current: dict[str, UrlRow],
) -> int:
    bulk = detect_bulk_lastmod_stamp(previous, current)
    bulk_ts = bulk.timestamp if bulk else None
    count = 0
    for url, row in current.items():
        if url not in previous:
            continue
        old = _lastmod_key(previous[url].lastmod)
        new = _lastmod_key(row.lastmod)
        if old is None or new is None or old == new:
            continue
        if bulk_ts and new == bulk_ts:
            continue
        count += 1
    return count


def diff_to_dict(diff: InventoryDiff) -> dict[str, Any]:
    out: dict[str, Any] = {
        "baseline": diff.baseline,
        "days_since_previous": diff.days_since_previous,
        "previous_run_id": diff.previous_run_id,
        "added": diff.added,
        "removed": diff.removed,
        "added_remainder": diff.added_remainder,
        "removed_remainder": diff.removed_remainder,
        "tier_c_added_count": diff.tier_c_added_count,
        "tier_c_removed_count": diff.tier_c_removed_count,
        "lastmod_changed_count": diff.lastmod_changed_count,
    }
    if diff.bulk_lastmod_ignored:
        out["bulk_lastmod_ignored"] = {
            "timestamp": diff.bulk_lastmod_ignored.timestamp,
            "url_count": diff.bulk_lastmod_ignored.url_count,
        }
    return out
