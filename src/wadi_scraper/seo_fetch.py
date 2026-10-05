from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx
import psycopg

from wadi_scraper.config import CompetitorConfig
from wadi_scraper.http_client import new_client
from wadi_scraper.diff import InventoryDiff, UrlRow
from wadi_scraper.extract import PageFields, fetch_page_fields
from wadi_scraper.fetch_queue import build_fetch_queue
from wadi_scraper.seo_diff import FieldChange, SeoDiffResult, diff_page_fields
from wadi_scraper.store import (
    get_last_page_snapshot,
    insert_page_snapshot,
    pick_rotation_urls,
)
from wadi_scraper.tiers import classify_url_tier, is_fetchable_tier


@dataclass
class SeoFetchStats:
    candidates: int = 0
    fetched: int = 0
    field_changes: list[FieldChange] = field(default_factory=list)


def _fetchable_urls(current: dict[str, UrlRow], competitor: CompetitorConfig) -> list[str]:
    out: list[str] = []
    for url, row in current.items():
        tier = classify_url_tier(url, row.page_type, competitor.tiers)
        if is_fetchable_tier(tier):
            out.append(url)
    return out


def run_seo_fetch(
    conn: psycopg.Connection,
    run_id: int,
    competitor: CompetitorConfig,
    current: dict[str, UrlRow],
    previous: dict[str, UrlRow] | None,
    diff: InventoryDiff,
    fetch_html: httpx.Client | None = None,
    page_fetcher: Optional[Callable[[str], PageFields]] = None,
) -> SeoFetchStats:
    stats = SeoFetchStats()
    if not current:
        return stats

    rot_pool = _fetchable_urls(current, competitor)
    rotate = pick_rotation_urls(
        conn,
        competitor.id,
        rot_pool,
        competitor.fetch.rotate_sample,
        before_run_id=run_id,
    )
    queue, total = build_fetch_queue(
        competitor, current, previous, diff, rotate_urls=rotate
    )
    stats.candidates = total

    own_client = fetch_html is None and page_fetcher is None
    client = None
    if page_fetcher is None:
        client = fetch_html or new_client()
    try:
        for url in queue:
            if page_fetcher is not None:
                fields = page_fetcher(url)
            else:
                assert client is not None
                fields = fetch_page_fields(url, client)
            prior = get_last_page_snapshot(conn, competitor.id, url, before_run_id=run_id)
            prior_fields = _snapshot_to_fields(prior) if prior else None
            stats.field_changes.extend(diff_page_fields(prior_fields, fields))
            insert_page_snapshot(conn, run_id, competitor.id, fields)
            stats.fetched += 1
            if competitor.fetch.delay_seconds > 0:
                time.sleep(competitor.fetch.delay_seconds)
    finally:
        if own_client and client is not None:
            client.close()

    return stats


def _snapshot_to_fields(row: tuple) -> PageFields:
    (
        url,
        final_url,
        http_status,
        title,
        meta_description,
        h1s_raw,
        canonical_url,
        meta_robots,
        low_confidence,
    ) = row
    h1s = h1s_raw if isinstance(h1s_raw, list) else json.loads(h1s_raw or "[]")
    return PageFields(
        url=url,
        final_url=final_url or url,
        http_status=int(http_status or 0),
        title=title or "",
        meta_description=meta_description or "",
        h1s=list(h1s),
        canonical_url=canonical_url or "",
        meta_robots=meta_robots or "",
        low_confidence=bool(low_confidence),
    )


def stats_to_meta(stats: SeoFetchStats) -> dict:
    return {
        "seo_candidates": stats.candidates,
        "seo_fetched": stats.fetched,
        "seo_field_change_count": len(stats.field_changes),
    }
