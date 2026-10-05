"""End-to-end proof: two site versions → URL + title/meta changes in report."""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
import pytest

from wadi_scraper.config import load_config
from wadi_scraper.env import load_env
from wadi_scraper.reporting import generate_report_for_run
from wadi_scraper.runner import run_ingest
from wadi_scraper.store import ensure_schema
from demo_site import BASE, demo_fetch, page_fields

BASE_STORED = BASE


@pytest.fixture
def db_conn():
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set (Neon .env.local)")
    with psycopg.connect(url) as conn:
        ensure_schema(conn)
        yield conn


@pytest.fixture
def demo_competitor():
    path = Path(__file__).resolve().parents[1] / "config" / "competitors_demo.yaml"
    return load_config(path).get("demo")


def test_proves_url_and_seo_change_detection(db_conn, demo_competitor):
    """
    Simulates a competitor site v1 → v2 without the public internet:
    - New page URL in sitemap
    - Removed page URL
    - Title + meta description changes on promo + sale pages
    """
    conn = db_conn
    app = load_config(Path(__file__).resolve().parents[1] / "config" / "competitors_demo.yaml")
    version = {"v": 1}

    def sitemap_fetch(url: str) -> tuple[int, bytes, str]:
        return demo_fetch(url, version["v"])

    def html_fetch(url: str):
        return page_fields(url, version["v"])

    run_id_v1, ingest1, status1 = run_ingest(
        conn,
        app,
        demo_competitor,
        fetch=sitemap_fetch,
        page_fetcher=html_fetch,
    )
    assert status1 == "ok"
    assert ingest1.pages_count >= 2

    version["v"] = 2
    run_id_v2, _, status2 = run_ingest(
        conn,
        app,
        demo_competitor,
        fetch=sitemap_fetch,
        page_fetcher=html_fetch,
    )
    assert status2 == "ok"

    md, report_json = generate_report_for_run(conn, app, run_id_v2, persist=False)
    payload = json.loads(report_json)
    inv = payload["competitors"][0]["inventory_diff"]
    seo = payload["competitors"][0]["seo"]

    added = inv["added"]
    removed = inv["removed"]
    assert f"{BASE_STORED}/pages/new-campaign" in added, f"expected new URL in added, got {added}"
    assert f"{BASE_STORED}/pages/about" in removed, f"expected removed about page, got {removed}"

    assert "Spring Mega Sale | Demo Brand" in md
    assert "Sale — Up to 30% Off" in md
    assert seo["changes"], "expected SEO field changes on run 2"

    fields_changed = {c["field"] for c in seo["changes"]}
    urls_changed = {c["url"] for c in seo["changes"]}
    assert "title" in fields_changed
    assert f"{BASE_STORED}/pages/promo-hub" in urls_changed

    assert "### Confirmed SEO field changes" in md
    assert "before:" in md and "after:" in md
    print("\n--- E2E PROOF REPORT (excerpt) ---\n")
    print(md)
