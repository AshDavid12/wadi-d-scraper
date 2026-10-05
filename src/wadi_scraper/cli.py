from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wadi_scraper.config import load_config
from wadi_scraper.env import load_env, require_database_url
from wadi_scraper.reporting import generate_report_for_run
from wadi_scraper.runner import run_ingest
from wadi_scraper.sitemap import IngestResult
from wadi_scraper.store import connect, ensure_schema, get_latest_run, get_report, get_run


def _print_summary(
    app_client: str,
    run_id: int,
    competitor_id: str,
    ingest: IngestResult,
    run_status: str,
) -> None:
    print(f"client: {app_client}")
    print(f"run_id: {run_id}")
    print(f"competitor: {competitor_id}")
    print(f"status: {run_status}")
    print(f"pages: {ingest.pages_count}")
    print(f"blogs: {ingest.blogs_count}")
    print(f"collections: {ingest.collections_count}")
    print(f"other: {ingest.other_count}")
    print(f"dropped_junk_locs: {ingest.dropped_junk}")
    print(f"skipped_sitemap_children: {len(ingest.skipped_sitemap_links)}")
    print(f"denied_sitemap_children: {len(ingest.denied_sitemap_links)}")
    print(f"http_requests: {len(ingest.requested_urls)}")


def cmd_run(args: argparse.Namespace) -> int:
    load_env()
    database_url = require_database_url()
    app = load_config()
    competitor_id = args.competitor
    try:
        competitor = app.get(competitor_id)
    except KeyError:
        print(f"Unknown competitor: {competitor_id}", file=sys.stderr)
        return 1
    if not competitor.enabled:
        print(f"Competitor {competitor_id} is disabled in config.", file=sys.stderr)
        return 1

    with connect(database_url) as conn:
        ensure_schema(conn)
        run_id, ingest, run_status = run_ingest(conn, app, competitor)
        run = get_run(conn, run_id)
        seo_meta = (run.meta if run else {}) or {}

    _print_summary(app.client, run_id, competitor_id, ingest, run_status)
    if run_status in ("ok", "partial"):
        print(
            f"seo_fetch: {seo_meta.get('seo_fetched', 0)} of "
            f"{seo_meta.get('seo_candidates', 0)} pages"
        )
        print(f"seo_field_changes: {seo_meta.get('seo_field_change_count', 0)}")
    print(f"report: run_id {run_id} (use `python -m wadi_scraper report --run-id {run_id}`)")
    return 0 if run_status in ("ok", "partial", "sitemap_error") else 1


def cmd_report(args: argparse.Namespace) -> int:
    load_env()
    database_url = require_database_url()
    app = load_config()

    with connect(database_url) as conn:
        ensure_schema(conn)
        if args.run_id:
            run_id = args.run_id
            if not get_run(conn, run_id):
                print(f"Run {run_id} not found.", file=sys.stderr)
                return 1
        else:
            latest = get_latest_run(conn, args.competitor)
            if not latest:
                print("No runs found.", file=sys.stderr)
                return 1
            run_id = latest.id

        if args.regenerate:
            md, _ = generate_report_for_run(conn, app, run_id, persist=True)
        else:
            md, js = get_report(conn, run_id)
            if not md:
                md, _ = generate_report_for_run(conn, app, run_id, persist=True)
            elif js is None:
                md, _ = generate_report_for_run(conn, app, run_id, persist=True)

        if args.write_report:
            out_dir = Path(args.write_report)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"summary-{run_id}.md").write_text(md, encoding="utf-8")
            _, js = get_report(conn, run_id)
            if js:
                import json

                (out_dir / f"summary-{run_id}.json").write_text(
                    json.dumps(js, indent=2), encoding="utf-8"
                )
            print(f"Wrote report to {out_dir}")

        print(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wadi-scraper")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Ingest sitemap snapshot for a competitor")
    run_p.add_argument(
        "--competitor",
        required=True,
        help="Competitor id (e.g. reebok)",
    )
    run_p.set_defaults(func=cmd_run)

    report_p = sub.add_parser("report", help="Show change report for a run")
    report_p.add_argument("--run-id", type=int, help="Run id (default: latest)")
    report_p.add_argument(
        "--competitor",
        help="With no run-id, use latest run for this competitor",
    )
    report_p.add_argument(
        "--write-report",
        metavar="DIR",
        help="Also write summary markdown/json files to this directory",
    )
    report_p.add_argument(
        "--regenerate",
        action="store_true",
        help="Rebuild report from stored snapshots",
    )
    report_p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
