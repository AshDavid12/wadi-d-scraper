from __future__ import annotations

import json
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import psycopg

from wadi_scraper.config import AppConfig, load_config
from wadi_scraper.env import load_env, require_database_url
from wadi_scraper.jobs import JobManager, default_job_manager
from wadi_scraper.report import format_datetime_utc
from wadi_scraper.store import (
    competitor_snapshot_number,
    connect,
    ensure_schema,
    get_report,
    get_run,
    list_runs,
)

_UI_DIR = Path(__file__).resolve().parent / "ui"


def ui_index_path() -> Path:
    return _UI_DIR / "report_viewer.html"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return format_datetime_utc(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def json_response(data: Any) -> bytes:
    return json.dumps(data, default=_json_default).encode("utf-8")


def api_competitors(app: AppConfig) -> dict[str, Any]:
    return {
        "client": app.client,
        "competitors": [
            {"id": c.id, "name": c.name, "enabled": c.enabled}
            for c in app.competitors
        ],
    }


def api_runs_list(
    conn: psycopg.Connection,
    *,
    competitor_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    rows = list_runs(conn, competitor_id=competitor_id, limit=limit)
    return [
        {
            "id": r.id,
            "snapshot_number": r.snapshot_number,
            "competitor_id": r.competitor_id,
            "status": r.status,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "counts": {
                "pages": r.pages_count,
                "blogs": r.blogs_count,
                "collections": r.collections_count,
                "other": r.other_count,
            },
            "has_report": r.has_report,
        }
        for r in rows
    ]


def api_run_report(
    conn: psycopg.Connection,
    app: AppConfig,
    run_id: int,
) -> dict[str, Any] | None:
    run = get_run(conn, run_id)
    if not run:
        return None
    md, js = get_report(conn, run_id)
    name = run.competitor_id
    try:
        name = app.get(run.competitor_id).name
    except KeyError:
        pass
    generated = None
    if js and isinstance(js, dict):
        generated = js.get("generated_at_utc_display")
    return {
        "run_id": run.id,
        "snapshot_number": competitor_snapshot_number(conn, run.competitor_id, run.id),
        "competitor_id": run.competitor_id,
        "competitor_name": name,
        "status": run.status,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "generated_at_utc": generated,
        "markdown": md or "",
        "has_report": bool(md),
    }


def dispatch_get(
    path: str,
    query: dict[str, list[str]],
    *,
    database_url: str,
    app: AppConfig,
    jobs: JobManager,
) -> tuple[int, str, bytes]:
    if path == "/" or path == "/index.html":
        html_path = ui_index_path()
        if not html_path.is_file():
            return 500, "text/plain", b"UI file missing (report_viewer.html)"
        return 200, "text/html; charset=utf-8", html_path.read_bytes()

    if path == "/api/competitors":
        return 200, "application/json", json_response(api_competitors(app))

    if path == "/api/runs":
        competitor = (query.get("competitor") or [None])[0]
        limit_raw = (query.get("limit") or ["50"])[0]
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 50
        with connect(database_url) as conn:
            ensure_schema(conn)
            payload = api_runs_list(conn, competitor_id=competitor, limit=limit)
        return 200, "application/json", json_response({"runs": payload})

    m = re.fullmatch(r"/api/runs/(\d+)/report", path)
    if m:
        run_id = int(m.group(1))
        with connect(database_url) as conn:
            ensure_schema(conn)
            payload = api_run_report(conn, app, run_id)
        if payload is None:
            return 404, "application/json", json_response({"error": "run not found"})
        return 200, "application/json", json_response(payload)

    m_job = re.fullmatch(r"/api/jobs/([a-f0-9]+)", path)
    if m_job:
        job_id = m_job.group(1)
        job = jobs.get(job_id)
        if not job:
            return 404, "application/json", json_response({"error": "job not found"})
        return 200, "application/json", json_response(jobs.to_dict(job))

    return 404, "application/json", json_response({"error": "not found"})


def dispatch_post(
    path: str,
    body: bytes,
    *,
    database_url: str,
    app: AppConfig,
    jobs: JobManager,
) -> tuple[int, str, bytes]:
    if path != "/api/runs":
        return 404, "application/json", json_response({"error": "not found"})

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return 400, "application/json", json_response({"error": "invalid JSON"})

    all_enabled = bool(payload.get("all_enabled"))
    competitor_id = payload.get("competitor_id")

    if all_enabled and competitor_id:
        return 400, "application/json", json_response(
            {"error": "use competitor_id or all_enabled, not both"}
        )

    if all_enabled:
        competitor_ids = [c.id for c in app.enabled()]
        if not competitor_ids:
            return 400, "application/json", json_response({"error": "no enabled competitors"})
    elif competitor_id:
        try:
            comp = app.get(str(competitor_id))
        except KeyError:
            return 400, "application/json", json_response({"error": "unknown competitor"})
        if not comp.enabled:
            return 400, "application/json", json_response({"error": "competitor is disabled"})
        competitor_ids = [comp.id]
    else:
        return 400, "application/json", json_response(
            {"error": "competitor_id or all_enabled required"}
        )

    if jobs.has_active_job():
        return 409, "application/json", json_response({"error": "a crawl is already running"})

    job_id = jobs.start(database_url, app, competitor_ids)
    if not job_id:
        return 409, "application/json", json_response({"error": "a crawl is already running"})
    return 202, "application/json", json_response({"job_id": job_id})


def make_handler(
    database_url: str,
    app: AppConfig,
    jobs: JobManager | None = None,
) -> type[BaseHTTPRequestHandler]:
    job_mgr = jobs or default_job_manager

    class ReportUIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                code, content_type, body = dispatch_get(
                    parsed.path,
                    parse_qs(parsed.query),
                    database_url=database_url,
                    app=app,
                    jobs=job_mgr,
                )
            except Exception as exc:
                code = 500
                content_type = "application/json"
                body = json_response({"error": str(exc)})
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            parsed = urlparse(self.path)
            try:
                code, content_type, body = dispatch_post(
                    parsed.path,
                    raw,
                    database_url=database_url,
                    app=app,
                    jobs=job_mgr,
                )
            except Exception as exc:
                code = 500
                content_type = "application/json"
                body = json_response({"error": str(exc)})
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[serve] {self.address_string()} {fmt % args}")

    return ReportUIHandler


def run_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    database_url: str | None = None,
    app: AppConfig | None = None,
    jobs: JobManager | None = None,
) -> None:
    load_env()
    db = database_url or require_database_url()
    cfg = app or load_config()
    handler = make_handler(db, cfg, jobs=jobs)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Report UI at {url} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
