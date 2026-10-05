from __future__ import annotations

from typing import Callable, Optional

import psycopg

from wadi_scraper.config import AppConfig, CompetitorConfig
from wadi_scraper.extract import PageFields
from wadi_scraper.reporting import build_inventory_diff, generate_report_for_run
from wadi_scraper.seo_diff import FieldChange
from wadi_scraper.seo_fetch import run_seo_fetch, stats_to_meta
from wadi_scraper.sitemap import (
    FetchFn,
    IngestResult,
    any_product_sitemap_requested,
    ingest_competitor_sitemap,
    ingest_run_status,
)
from wadi_scraper.store import (
    create_run,
    finish_run,
    get_previous_successful_run,
    insert_url_observations,
    load_url_observations,
)


def _changes_to_json(changes: list[FieldChange]) -> list[dict]:
    return [
        {
            "url": c.url,
            "field": c.field,
            "before": c.before,
            "after": c.after,
            "low_confidence": c.low_confidence,
        }
        for c in changes
    ]


def run_ingest(
    conn: psycopg.Connection,
    app: AppConfig,
    competitor: CompetitorConfig,
    fetch: FetchFn | None = None,
    page_fetcher: Optional[Callable[[str], PageFields]] = None,
) -> tuple[int, IngestResult, str]:
    run_id = create_run(conn, competitor.id)
    ingest = ingest_competitor_sitemap(competitor, fetch=fetch)
    try:
        product_hits = any_product_sitemap_requested(ingest.requested_urls, competitor)
        if product_hits:
            finish_run(
                conn,
                run_id,
                status="failed",
                ingest=ingest,
                error_message=f"Product sitemap requested: {product_hits[0]}",
                extra_meta={"product_sitemap_violations": product_hits},
            )
            generate_report_for_run(conn, app, run_id)
            raise RuntimeError("Product sitemap URL was requested")

        run_status = ingest_run_status(ingest)
        error_message = None
        if run_status == "sitemap_error":
            error_message = "Sitemap ingest failed (no URLs stored)."
            if ingest.sitemap_failures:
                u, code = ingest.sitemap_failures[0]
                error_message = f"Sitemap fetch failed: {u} → HTTP {code}"
        elif run_status == "partial":
            error_message = "Some sitemap fetches failed; partial inventory stored."

        prev_run = get_previous_successful_run(conn, competitor.id, run_id)
        previous_urls = (
            load_url_observations(conn, prev_run.id) if prev_run else None
        )

        if run_status in ("ok", "partial"):
            insert_url_observations(conn, run_id, competitor.id, ingest.entries)
            current_urls = load_url_observations(conn, run_id)
            diff = build_inventory_diff(conn, competitor, run_id, run_status)
            seo_stats = run_seo_fetch(
                conn,
                run_id,
                competitor,
                current_urls,
                previous_urls,
                diff,
                page_fetcher=page_fetcher,
            )
            seo_meta = stats_to_meta(seo_stats)
            seo_meta["seo_field_changes"] = _changes_to_json(seo_stats.field_changes)
            seo_meta["html_mode"] = competitor.html_mode
        else:
            seo_meta = {}

        finish_run(
            conn,
            run_id,
            status=run_status,
            ingest=ingest,
            error_message=error_message,
            extra_meta=seo_meta,
        )
        generate_report_for_run(conn, app, run_id)
        return run_id, ingest, run_status
    except Exception as exc:
        if str(exc) != "Product sitemap URL was requested":
            conn.execute(
                """
                UPDATE runs SET status = %s, error_message = %s, finished_at = NOW()
                WHERE id = %s
                """,
                ("failed", str(exc), run_id),
            )
            conn.commit()
        raise
