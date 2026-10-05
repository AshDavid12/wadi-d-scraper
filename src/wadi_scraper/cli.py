from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wadi_scraper.config import load_config
from wadi_scraper.env import load_env, require_database_url
from wadi_scraper.probe import format_probe_report, probe_competitor
from wadi_scraper.reporting import generate_report_for_run
from wadi_scraper.runner import run_ingest
from wadi_scraper.sitemap import IngestResult
from wadi_scraper.serve import run_server
from wadi_scraper.store import connect, ensure_schema, get_latest_run, get_report, get_run


def _print_summary(
    app_client: str,
    run_id: int,
    competitor_id: str,
    ingest: IngestResult,
    run_status: str,
) -> None:
    print(f"client: {app_client}")
    print(f"run_id: {run_id}  (database id; see report snapshot # for brand sequence)")
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


def _run_one_competitor(
    app,
    conn,
    competitor_id: str,
) -> tuple[int, IngestResult, str]:
    competitor = app.get(competitor_id)
    if not competitor.enabled:
        raise ValueError(f"disabled:{competitor_id}")
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
    print("")
    return run_id, ingest, run_status


def cmd_run(args: argparse.Namespace) -> int:
    load_env()
    database_url = require_database_url()
    app = load_config()

    targets: list[str]
    if args.competitor:
        targets = [args.competitor]
    else:
        targets = [c.id for c in app.enabled()]
        if not targets:
            print("No enabled competitors in config.", file=sys.stderr)
            return 1

    exit_code = 0
    with connect(database_url) as conn:
        ensure_schema(conn)
        for competitor_id in targets:
            try:
                _, _, run_status = _run_one_competitor(app, conn, competitor_id)
            except KeyError:
                print(f"Unknown competitor: {competitor_id}", file=sys.stderr)
                exit_code = 1
                continue
            except ValueError as exc:
                if str(exc).startswith("disabled:"):
                    print(f"Competitor {competitor_id} is disabled in config.", file=sys.stderr)
                else:
                    print(str(exc), file=sys.stderr)
                exit_code = 1
                continue
            except Exception as exc:
                print(f"{competitor_id} failed: {exc}", file=sys.stderr)
                exit_code = 1
                continue
            if run_status not in ("ok", "partial", "sitemap_error"):
                exit_code = 1
    return exit_code


def cmd_probe(args: argparse.Namespace) -> int:
    load_env()
    app = load_config()
    if args.competitor:
        ids = [args.competitor]
    else:
        ids = [c.id for c in app.competitors]

    exit_code = 0
    for cid in ids:
        try:
            competitor = app.get(cid)
        except KeyError:
            print(f"Unknown competitor: {cid}", file=sys.stderr)
            exit_code = 1
            continue
        result = probe_competitor(competitor)
        print(format_probe_report(result))
        print("")
        if args.require_enabled and not competitor.enabled:
            continue
        if competitor.enabled and not result.ok:
            exit_code = 1
        if args.require_enabled and competitor.enabled and not result.ok:
            exit_code = 1
    return exit_code


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


def cmd_serve(args: argparse.Namespace) -> int:
    load_env()
    if args.open:
        import threading
        import webbrowser

        url = f"http://{args.host}:{args.port}/"
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    run_server(host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wadi-scraper")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Ingest sitemap snapshot for one or all enabled competitors")
    run_p.add_argument(
        "--competitor",
        help="Competitor id (e.g. reebok). Omit to run all enabled brands.",
    )
    run_p.set_defaults(func=cmd_run)

    probe_p = sub.add_parser(
        "probe",
        help="Check robots + sitemap index reachability (no child sitemap downloads)",
    )
    probe_p.add_argument(
        "--competitor",
        help="Single brand id. Omit to probe every brand in config.",
    )
    probe_p.add_argument(
        "--require-enabled",
        action="store_true",
        help="Exit 1 if any enabled brand fails probe",
    )
    probe_p.set_defaults(func=cmd_probe)

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

    serve_p = sub.add_parser("serve", help="Local web UI for browsing stored reports")
    serve_p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=8787, help="Port (default: 8787)")
    serve_p.add_argument(
        "--open",
        action="store_true",
        help="Open browser after starting",
    )
    serve_p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
