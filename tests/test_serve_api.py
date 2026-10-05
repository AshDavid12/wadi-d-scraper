from __future__ import annotations

from unittest.mock import MagicMock, patch

from wadi_scraper.config import AppConfig, CompetitorConfig
from wadi_scraper.serve import api_competitors, api_run_report, api_runs_list, dispatch_get
from wadi_scraper.store import RunSummary


def _app() -> AppConfig:
    return AppConfig(
        client="Nike",
        competitors=[
            CompetitorConfig(id="reebok", name="Reebok", enabled=True),
        ],
    )


def test_api_competitors():
    data = api_competitors(_app())
    assert data["client"] == "Nike"
    assert data["competitors"][0]["id"] == "reebok"


def test_api_runs_list():
    conn = MagicMock()
    summary = RunSummary(
        id=5,
        competitor_id="reebok",
        status="ok",
        started_at=None,
        finished_at=None,
        pages_count=10,
        blogs_count=1,
        collections_count=2,
        other_count=0,
        has_report=True,
    )
    with patch("wadi_scraper.serve.list_runs", return_value=[summary]):
        rows = api_runs_list(conn, competitor_id="reebok", limit=10)
    assert rows[0]["id"] == 5
    assert rows[0]["has_report"] is True


def test_dispatch_get_index():
    app = _app()
    code, ct, body = dispatch_get("/", {}, database_url="postgresql://x", app=app)
    assert code == 200
    assert b"Competitor reports" in body
    assert "text/html" in ct


def test_api_run_report_missing():
    conn = MagicMock()
    with patch("wadi_scraper.serve.get_run", return_value=None):
        assert api_run_report(conn, _app(), 999) is None
