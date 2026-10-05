from __future__ import annotations

from wadi_scraper.config import CompetitorConfig
from wadi_scraper.diff import InventoryDiff, UrlRow, detect_bulk_lastmod_stamp
from wadi_scraper.tiers import TIER_A, TIER_B, classify_url_tier, is_fetchable_tier


def _lastmod_changed(
    url: str,
    previous: dict[str, UrlRow],
    current: dict[str, UrlRow],
    bulk_ts: str | None,
) -> bool:
    if url not in previous or url not in current:
        return False
    old = previous[url].lastmod
    new = current[url].lastmod
    if old is None or new is None or old == new:
        return False
    if bulk_ts and new.isoformat() == bulk_ts:
        return False
    return True


def build_fetch_queue(
    competitor: CompetitorConfig,
    current: dict[str, UrlRow],
    previous: dict[str, UrlRow] | None,
    diff: InventoryDiff,
    *,
    rotate_urls: list[str],
) -> tuple[list[str], int]:
    """Return (ordered urls to fetch, total candidates before cap)."""
    max_pages = competitor.fetch.max_pages
    bulk_ts = diff.bulk_lastmod_ignored.timestamp if diff.bulk_lastmod_ignored else None
    if previous and not bulk_ts:
        bulk_stamp = detect_bulk_lastmod_stamp(previous, current)
        bulk_ts = bulk_stamp.timestamp if bulk_stamp else None

    def tier_of(u: str) -> str:
        row = current.get(u) or (previous or {}).get(u)
        pt = row.page_type if row else "other"
        return classify_url_tier(u, pt, competitor.tiers)

    candidates: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if url in seen:
            return
        if not is_fetchable_tier(tier_of(url)):
            return
        seen.add(url)
        candidates.append(url)

    if diff.baseline or previous is None:
        for url in sorted(current.keys()):
            add(url)
    else:
        prev_urls = set(previous.keys())
        for url in sorted(set(current.keys()) - prev_urls):
            add(url)
        for url in current:
            if url in previous and _lastmod_changed(url, previous, current, bulk_ts):
                add(url)
        for url in rotate_urls:
            add(url)

    tier_a = [u for u in candidates if tier_of(u) == TIER_A]
    tier_b = [u for u in candidates if tier_of(u) == TIER_B]
    ordered = tier_a + [u for u in tier_b if u not in tier_a]
    total = len(ordered)
    return ordered[:max_pages], total
