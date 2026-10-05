from __future__ import annotations

from datetime import datetime

import psycopg

from wadi_scraper.config import AppConfig, CompetitorConfig
from wadi_scraper.diff import InventoryDiff, diff_inventory
from wadi_scraper.report import CompetitorReportBlock, SeoReportSection, serialize_report
from wadi_scraper.seo_diff import FieldChange
from wadi_scraper.tiers import classify_url_tier
from wadi_scraper.store import (
    competitor_snapshot_number,
    get_previous_successful_run,
    get_run,
    load_url_observations,
    save_report,
)


def _days_between(a: datetime | None, b: datetime | None) -> int | None:
    if not a or not b:
        return None
    delta = b - a
    return max(0, delta.days)


def _failures_from_meta(meta: dict) -> list[tuple[str, int]]:
    raw = meta.get("sitemap_failures") or []
    out: list[tuple[str, int]] = []
    for item in raw:
        if isinstance(item, dict):
            out.append((item["url"], int(item["http_status"])))
    return out


def _seo_from_meta(meta: dict) -> SeoReportSection:
    changes_raw = meta.get("seo_field_changes") or []
    changes: list[FieldChange] = []
    for item in changes_raw:
        if isinstance(item, dict):
            changes.append(
                FieldChange(
                    url=item["url"],
                    field=item["field"],
                    before=item.get("before", ""),
                    after=item.get("after", ""),
                    low_confidence=bool(item.get("low_confidence")),
                )
            )
    return SeoReportSection(
        candidates=int(meta.get("seo_candidates") or 0),
        fetched=int(meta.get("seo_fetched") or 0),
        field_changes=changes,
        html_mode=str(meta.get("html_mode") or "static"),
    )


def build_inventory_diff(
    conn: psycopg.Connection,
    competitor: CompetitorConfig,
    current_run_id: int,
    current_status: str,
) -> InventoryDiff:
    if current_status == "sitemap_error":
        return InventoryDiff(baseline=False, days_since_previous=None, previous_run_id=None)

    prev = get_previous_successful_run(conn, competitor.id, current_run_id)
    current_urls = load_url_observations(conn, current_run_id)

    if prev is None:
        return InventoryDiff(baseline=True, days_since_previous=None, previous_run_id=None)

    prev_urls = load_url_observations(conn, prev.id)

    def tier_fn(url: str, page_type: str) -> str:
        return classify_url_tier(url, page_type, competitor.tiers)

    diff = diff_inventory(prev_urls, current_urls, tier_fn=tier_fn)
    diff.previous_run_id = prev.id
    current_run = get_run(conn, current_run_id)
    if current_run and prev.finished_at and current_run.started_at:
        diff.days_since_previous = _days_between(prev.finished_at, current_run.started_at)
    return diff


def generate_report_for_run(
    conn: psycopg.Connection,
    app: AppConfig,
    run_id: int,
    *,
    persist: bool = True,
) -> tuple[str, str]:
    run = get_run(conn, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    try:
        competitor = app.get(run.competitor_id)
    except KeyError:
        competitor = CompetitorConfig(
            id=run.competitor_id,
            name=run.competitor_id,
            enabled=True,
        )

    diff = build_inventory_diff(conn, competitor, run_id, run.status)
    meta = run.meta
    denied = list(meta.get("denied_sitemap_links") or [])

    block = CompetitorReportBlock(
        competitor_id=run.competitor_id,
        competitor_name=competitor.name,
        run_id=run.id,
        status=run.status,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        pages_count=run.pages_count,
        blogs_count=run.blogs_count,
        collections_count=run.collections_count,
        other_count=run.other_count,
        skipped_sitemap_links=run.skipped_sitemap_links,
        denied_sitemap_links=denied,
        sitemap_failures=_failures_from_meta(meta),
        diff=diff,
        seo=_seo_from_meta(meta),
        snapshot_number=competitor_snapshot_number(conn, run.competitor_id, run.id),
    )

    md, report_json = serialize_report(app.client, [block])
    if persist:
        save_report(conn, run_id, md, report_json)
    return md, report_json
