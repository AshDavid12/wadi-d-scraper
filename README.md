# wadi-d-scraper

**Competitor sitemap tracker** for Nike: discover what changed on rival footwear sites between manual runs—new and removed marketing URLs, sitemap signals, and selected on-page SEO fields—without building a product catalog or storing sitemap XML on disk.

Built for US competitors on Shopify-style sitemaps (Reebok live today; Hoka, Adidas, Brooks, and Asics planned in config).

---

## What it does

Each **`run`** for a configured competitor:

1. **Discovers sitemaps** from `robots.txt` / configured seeds, walks the sitemap index, and applies allow/deny rules (e.g. pages, blogs, collections **yes**; product sitemaps **never** fetched).
2. **Normalizes URLs** (scheme, host, fragments, junk paths) and classifies each URL (page, blog, collection, other).
3. **Stores a snapshot** of the URL inventory in **Postgres** (Neon), keyed by run id and competitor.
4. **Diffs** the current snapshot against the **previous successful run** for that competitor: added, removed, tier-C merchandising counts, bulk vs selective `lastmod` changes.
5. **Fetches HTML** for a capped set of Tier A/B URLs (default **50** per run), extracts title, meta description, H1s, canonical, and meta robots, and compares to the last stored page snapshot.
6. **Writes a report** (markdown + JSON) on the `runs` row, with **Generated (UTC)** timestamp; optional export to disk via CLI.

Runs are **manual only** (no cron). Data lives in the database, not as local competitor dumps.

```text
robots + sitemap index → filtered URL list → Postgres snapshot
                              ↓
         diff vs previous run → report (inventory + SEO changes)
                              ↓
         capped HTML fetch → page_snapshots → field-level SEO diff
```

---

## Features

| Area | Behavior |
|------|----------|
| **Sitemap ingest** | Index recursion, gzip, Shopify-style URLs; child sitemaps filtered by regex allow/deny |
| **Product sitemap guard** | Product sitemap URLs must never be requested; run fails if violated |
| **URL tiers** | **Tier A/B** — fetchable marketing URLs; **Tier C** — hash-style collection slugs counted only, not listed in add/remove or fetched |
| **Inventory diff** | Added / removed URLs; baseline on first successful run; bulk `lastmod` stamp detection |
| **SEO extraction** | `<title>`, meta description, H1, canonical, robots from static HTML |
| **SEO diff** | Per-field before/after in report when a URL is refetched and content changed |
| **Fetch queue** | New URLs, selective `lastmod` changes, plus optional rotation sample (`fetch.rotate_sample`) |
| **Run status** | `ok`, `partial` (some sitemap failures), `sitemap_error`, `failed` |
| **Reporting** | Markdown + JSON; regenerate from DB without re-crawling (`report --regenerate`) |
| **Config** | `config/competitors.yaml` — per-brand hosts, patterns, fetch caps, tier keywords |

### CLI

| Command | Purpose |
|---------|---------|
| `python -m wadi_scraper run --competitor <id>` | Live crawl + snapshot + SEO fetch + report |
| `python -m wadi_scraper report --run-id <n>` | Print stored report for a run |
| `python -m wadi_scraper report --competitor reebok` | Latest run for that competitor |
| `python -m wadi_scraper report --run-id <n> --write-report ./out` | Export markdown/JSON files |
| `python -m wadi_scraper report --run-id <n> --regenerate` | Rebuild report from existing DB rows |

Environment: `DATABASE_URL` (required for run/report). Optional `WADI_CONFIG` to point at another YAML (e.g. demo config).

### Live Reebok notes

- Run from a **normal office/home network**. Datacenter or VPN IPs often get **403** on competitor sites.
- SEO changes on live sites appear when URLs are **new**, **`lastmod` changes** (not a site-wide stamp), or hit the **rotation sample**—not every URL on every run.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Link Neon (writes `DATABASE_URL` to `.env.local`; see `.env.example`):

```bash
neon link
```

Schema in `sql/*.sql` is applied automatically on first connect.

---

## Usage (production config)

```bash
source .venv/bin/activate
set -a && source .env.local && set +a

python -m wadi_scraper run --competitor reebok
python -m wadi_scraper report --run-id 1
python -m wadi_scraper report --competitor reebok
python -m wadi_scraper report --run-id 2 --write-report ./out
```

After `run`, the CLI prints run id, inventory counts, HTTP request count, SEO fetch stats, and how to view the report.

---

## Tests

### Quick run (no database, no live crawl)

```bash
pytest
```

**~20 tests** use fixtures and pure logic—no `DATABASE_URL` required:

| Module | Covers |
|--------|--------|
| `test_sitemap.py` | Child sitemap allow/deny; product sitemap never fetched |
| `test_sitemap_error.py` | All sitemap 403 → `sitemap_error` |
| `test_normalize.py` | URL normalization |
| `test_diff.py` | Baseline, add/remove, bulk lastmod |
| `test_tiers.py` | Tier A/B/C classification |
| `test_fetch_queue.py` | Cap at 50, Tier C excluded from queue and diff lists |
| `test_extract.py` | HTML field extraction and change pairing |
| `test_report.py` | Markdown for baseline and sitemap errors |

### Local proof test (URL + SEO change detection)

Proves the **full pipeline** (ingest → Postgres → diff → SEO fetch → report) without real competitors. A fake site at `127.0.0.1:8765` goes **v1 → v2**; the second run should show:

- **Added:** `/pages/new-campaign`
- **Removed:** `/pages/about`
- **SEO:** title / meta / H1 on promo hub; title on sale collection (after demo `lastmod` bumps)

**Needs:** setup above + `DATABASE_URL` in `.env.local`.

```bash
source .venv/bin/activate
set -a && source .env.local && set +a
```

**Option A — pytest (CI-friendly)**  
In-memory sitemap/HTML; same code path as production:

```bash
pytest tests/test_e2e_proven.py -v -s
```

**Option B — real HTTP + script**  
Starts `demo/local_server.py` as v1, ingests, restarts as v2, ingests, prints report:

```bash
python scripts/prove_scraper_e2e.py
```

Use **http://** only (demo server is not HTTPS). Ignore stray TLS probe noise in the server log.

**Option C — browse the demo site**

```bash
DEMO_VERSION=1 python demo/local_server.py
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Restart with `DEMO_VERSION=2` to see content and sitemap membership change.

| File | Role |
|------|------|
| `tests/demo_site.py` | v1/v2 sitemap + HTML |
| `demo/local_server.py` | HTTP server on port 8765 |
| `config/competitors_demo.yaml` | Demo competitor (`normalize.scheme: http`) |
| `tests/test_e2e_proven.py` | Automated proof |
| `scripts/prove_scraper_e2e.py` | Two-run script |

---

## Repository layout

```text
config/competitors.yaml      # Production competitors (Reebok enabled)
config/competitors_demo.yaml # Local proof competitor
sql/                         # Postgres migrations
src/wadi_scraper/            # Package (sitemap, diff, fetch, report, CLI)
tests/                       # Unit + e2e proof tests
demo/                        # Local demo HTTP server
scripts/prove_scraper_e2e.py # Manual full HTTP proof
```

---

## Roadmap

Phase 4 (in progress): full configs and CI fixtures for remaining brands, `probe` CLI, multi-brand runs, and README sign-off checklist. See `.cursor/plans/competitor_sitemap_tracker_ad29f2be.plan.md`.
