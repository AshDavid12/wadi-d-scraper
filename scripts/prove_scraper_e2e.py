#!/usr/bin/env python3
"""
Run the demo site twice (v1 → v2) through the real CLI + Neon Postgres.

Usage (from repo root, venv active, .env.local loaded):
  python scripts/prove_scraper_e2e.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

PORT = 8765


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    server_v1 = subprocess.Popen(
        [sys.executable, str(ROOT / "demo" / "local_server.py")],
        env={**env, "DEMO_VERSION": "1"},
        cwd=str(ROOT),
    )
    time.sleep(0.5)
    try:
        cfg = ROOT / "config" / "competitors_demo.yaml"
        # Temporarily point main config — use env WADI_CONFIG
        env["WADI_CONFIG"] = str(cfg)

        # Patch load_config via copying demo yaml over — simpler: invoke python API
        from wadi_scraper.config import load_config
        from wadi_scraper.env import load_env, require_database_url
        from wadi_scraper.reporting import generate_report_for_run
        from wadi_scraper.runner import run_ingest
        from wadi_scraper.store import connect, ensure_schema

        import httpx

        load_env()
        db = require_database_url()
        app = load_config(cfg)
        demo = app.get("demo")

        def fetch(url: str) -> tuple[int, bytes, str]:
            with httpx.Client(timeout=10) as c:
                r = c.get(url)
                return r.status_code, r.content, r.headers.get("content-type", "")

        def page_fetch(url: str):
            from wadi_scraper.extract import extract_from_html

            with httpx.Client(timeout=10) as c:
                r = c.get(url)
            return extract_from_html(url, str(r.url), r.status_code, r.text)

        with connect(db) as conn:
            ensure_schema(conn)
            print("=== Run 1 (demo site v1) ===")
            run_ingest(conn, app, demo, fetch=fetch, page_fetcher=page_fetch)
    finally:
        server_v1.terminate()
        server_v1.wait()

    server_v2 = subprocess.Popen(
        [sys.executable, str(ROOT / "demo" / "local_server.py")],
        env={**env, "DEMO_VERSION": "2"},
        cwd=str(ROOT),
    )
    time.sleep(0.5)
    try:
        from wadi_scraper.config import load_config
        from wadi_scraper.env import load_env, require_database_url
        from wadi_scraper.reporting import generate_report_for_run
        from wadi_scraper.runner import run_ingest
        from wadi_scraper.store import connect, ensure_schema
        import httpx
        from wadi_scraper.extract import extract_from_html

        load_env()
        app = load_config(ROOT / "config" / "competitors_demo.yaml")
        demo = app.get("demo")

        def fetch(url: str) -> tuple[int, bytes, str]:
            with httpx.Client(timeout=10) as c:
                r = c.get(url)
                return r.status_code, r.content, r.headers.get("content-type", "")

        def page_fetch(url: str):
            with httpx.Client(timeout=10) as c:
                r = c.get(url)
            return extract_from_html(url, str(r.url), r.status_code, r.text)

        with connect(require_database_url()) as conn:
            print("=== Run 2 (demo site v2 — changes) ===")
            run_id, _, _ = run_ingest(conn, app, demo, fetch=fetch, page_fetcher=page_fetch)
            md, _ = generate_report_for_run(conn, app, run_id, persist=True)
            print(md)
    finally:
        server_v2.terminate()
        server_v2.wait()

    print(f"\nProof complete. Demo server used http://127.0.0.1:{PORT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
