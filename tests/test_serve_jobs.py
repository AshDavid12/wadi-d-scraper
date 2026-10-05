from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

from wadi_scraper.config import AppConfig, CompetitorConfig
from wadi_scraper.jobs import JobManager
from wadi_scraper.serve import dispatch_post
from wadi_scraper.sitemap import IngestResult


def _app() -> AppConfig:
    return AppConfig(
        client="Nike",
        competitors=[
            CompetitorConfig(id="reebok", name="Reebok", enabled=True),
            CompetitorConfig(id="hoka", name="Hoka", enabled=False),
        ],
    )


def test_post_run_disabled_competitor():
    jobs = JobManager()
    code, _, body = dispatch_post(
        "/api/runs",
        b'{"competitor_id":"hoka"}',
        database_url="postgresql://x",
        app=_app(),
        jobs=jobs,
    )
    assert code == 400
    assert b"disabled" in body


def test_post_run_conflict_when_active():
    jobs = JobManager()
    jobs._active_job_id = "busy"
    code, _, _ = dispatch_post(
        "/api/runs",
        b'{"competitor_id":"reebok"}',
        database_url="postgresql://x",
        app=_app(),
        jobs=jobs,
    )
    assert code == 409


def test_dispatch_post_returns_job_id():
    jobs = JobManager()
    jobs.start = MagicMock(return_value="job123")
    code, _, body = dispatch_post(
        "/api/runs",
        b'{"competitor_id":"reebok"}',
        database_url="postgresql://x",
        app=_app(),
        jobs=jobs,
    )
    assert code == 202
    assert json.loads(body.decode())["job_id"] == "job123"


def test_job_manager_runs_mock_ingest(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(
        "wadi_scraper.jobs.connect",
        lambda _url: MagicMock(__enter__=lambda s: conn, __exit__=lambda *a: None),
    )
    monkeypatch.setattr("wadi_scraper.jobs.ensure_schema", lambda _c: None)

    jobs = JobManager()
    ingest = IngestResult(pages_count=7, blogs_count=1)

    def fake_ingest(c, app, competitor):
        return 42, ingest, "ok"

    job_id = jobs.start("postgresql://x", _app(), ["reebok"], run_fn=fake_ingest)
    assert job_id
    for _ in range(100):
        job = jobs.get(job_id)
        assert job is not None
        if job.status in ("done", "failed"):
            break
        time.sleep(0.02)
    job = jobs.get(job_id)
    assert job is not None
    assert job.status == "done"
    assert job.run_ids == [42]
    assert any("pages=7" in line for line in job.lines)
