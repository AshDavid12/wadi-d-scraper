# wadi-d-scraper

Nike competitor sitemap tracker (Phase 1: Reebok ingest → Neon Postgres).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Neon: `neon link` writes `DATABASE_URL` to `.env.local` (see `.env.example`).

Apply schema automatically on first run.

## Manual run + report (Phase 1–3)

```bash
python -m wadi_scraper run --competitor reebok
python -m wadi_scraper report --run-id 1
python -m wadi_scraper report --competitor reebok   # latest run
python -m wadi_scraper report --run-id 2 --write-report ./out
```

Each `run` stores a versioned snapshot in Postgres, diffs against the **previous successful** run, fetches up to **50** Tier A/B pages for title/meta/H1 changes, and saves markdown/JSON on the `runs` row. Hash-style collection URLs (Tier C) are counted only, not listed or fetched. No sitemap files on disk.

## Tests

```bash
pytest
```

Uses HTTP fixtures only (no live crawl, no `DATABASE_URL` required).
