# wadi-d-scraper

**Competitor sitemap tracker** for Nike: discover what changed on rival footwear sites between manual runs—new and removed marketing URLs, sitemap signals, and selected on-page SEO fields—without building a product catalog or storing sitemap XML on disk.

Tracks **five US competitors**: Reebok, Hoka, Adidas, Brooks, and Asics. Brand-specific rules live in YAML (Shopify, SFCC, glass, custom)—not hard-coded in Python.

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
| **Sitemap ingest** | Index recursion, gzip and Brotli, Shopify-style URLs; child sitemaps filtered by regex allow/deny |
| **Product sitemap guard** | Product sitemap URLs must never be requested; run fails if violated |
| **URL tiers** | **Tier A/B** — fetchable marketing URLs; **Tier C** — hash-style collection slugs counted only, not listed in add/remove or fetched |
| **Inventory diff** | Added / removed URLs; baseline on first successful run; bulk `lastmod` stamp detection |
| **SEO extraction** | `<title>`, meta description, H1, canonical, robots from static HTML. A title with an empty H1 is marked **low confidence** (heading likely added by JavaScript) |
| **SEO diff** | Per-field before/after in report when a URL is refetched and content changed |
| **Fetch queue** | New URLs, selective `lastmod` changes, plus optional rotation sample (`fetch.rotate_sample`) |
| **Bot wall** | HTTP 403 / 406 / 429 with captcha or challenge HTML is recorded as a wall on probe and ingest. No retry and no captcha solving |
| **Run status** | `ok`, `partial` (some sitemap failures), `sitemap_error`, `failed` |
| **Reporting** | Markdown + JSON; lists at most 100 added and 100 removed URLs (the rest are a count) and up to 50 SEO field changes. Regenerate from DB without re-crawling (`report --regenerate`) |
| **Report UI** | Local browser at `serve`: snapshot list, rendered markdown with inline help, start crawls, and a **How this works** guide |
| **Config** | `config/competitors.yaml` — per-brand hosts, patterns, US loc filters, fetch caps, tiers |
| **Multi-brand** | `run` with no `--competitor` runs all **enabled** brands; failures do not stop siblings |
| **Probe** | `probe` checks robots + index XML and previews allow/deny/skip **without** downloading child sitemaps |

### Competitor profiles (summary)

| Brand | Platform | US focus | Notes |
|-------|----------|----------|--------|
| Reebok | Shopify | `www.reebok.com` | Reference brand; `robots` + Shopify child names |
| Hoka | SFCC | `/en/us/` locs | `seeds_only`: `sitemap_index_all.xml`; deny hreflang/static. **Often 403 on the index even when `robots.txt` is 200** (bot wall on sitemap URLs—not a YAML typo). |
| Adidas | glass | `/us/` locs | US glass index seed; allow PLP + blog sitemaps only |
| Brooks | custom | `/en_us/` locs | Deny CA/GB sitemap children and loc prefixes |
| Asics | custom | `/us/en-us/` locs | US content sitemap; deny JP/CA product indexes |

Only brands with `enabled: true` are included in `run` and **Run all enabled**. The checked-in `config/competitors.yaml` has **all five enabled**. A brand that fails `probe` still produces a `sitemap_error` report. Set `enabled: false` until probe succeeds on your network if you do not want those error runs.

### CLI

| Command | Purpose |
|---------|---------|
| `python -m wadi_scraper probe` | Probe all brands in config (index + child preview) |
| `python -m wadi_scraper probe --competitor hoka` | Single-brand probe |
| `python -m wadi_scraper probe --require-enabled` | Exit 1 if any **enabled** brand fails probe |
| `python -m wadi_scraper run --competitor reebok` | Live crawl + snapshot + SEO fetch + report |
| `python -m wadi_scraper run` | Run **all enabled** competitors (continue on error) |
| `python -m wadi_scraper report --run-id <n>` | Print stored report for a run |
| `python -m wadi_scraper report --competitor reebok` | Latest run for that competitor |
| `python -m wadi_scraper report --run-id <n> --write-report ./out` | Export markdown/JSON files |
| `python -m wadi_scraper report --run-id <n> --regenerate` | Rebuild report from existing DB rows |
| `python -m wadi_scraper serve` | **Local report UI** at http://127.0.0.1:8787/ (browse reports and start crawls) |
| `python -m wadi_scraper serve --open` | Start UI and open your browser |

Environment: `DATABASE_URL` (required for run/report/serve). Optional `WADI_CONFIG` to point at another YAML (e.g. demo config).

### Report UI (local)

Browse stored reports, read the plain-English guide, and **start crawls** from the browser (same pipeline as CLI `run`).

```bash
set -a && source .env.local && set +a
python -m wadi_scraper serve --open
```

**Reports**

- Header shows the client (Nike) and a pill for each brand. Disabled brands are marked off.
- Filter the snapshot list by brand. Each row is **snapshot #N** for that brand, with status and page / blog / collection counts.
- Open a row to render the stored markdown (same text as `report --run-id`). **Raw markdown** shows the source.
- The status badge explains `ok`, `partial`, `sitemap_error`, and `failed`. Terms in the report (bulk lastmod, tier C, SEO fields, baseline, and similar) have inline help.
- **Run selected brand** / **Run all enabled** start one background job with a live log and open the new report when it finishes. A disabled brand cannot be started. A second crawl returns HTTP 409 until the first finishes.

**How this works**

- The second tab renders [`docs/how-this-project-works.md`](docs/how-this-project-works.md) from `GET /api/guide`. The server prefers the repo file, so edits show up without a reinstall. The same file is packaged into the wheel.

Binds **127.0.0.1** by default. Do not expose on `0.0.0.0` without auth — the UI reads the database and triggers live fetches.

**Run numbering:** The UI shows **snapshot #N** per brand (1st Reebok run, 2nd Reebok run, …). The global **database run id** (e.g. 37) still exists for CLI `--run-id` and foreign keys; it grows with every test/demo ingest on that Neon branch. Use a **dev Neon branch** for experiments to keep production ids tidy.

### Manual workflow (office / home network)

1. `probe --require-enabled` — every enabled brand should show **Probe OK: yes**, index HTTP **200**, and at least one **allow** child.
2. `run` or `run --competitor …` — stores snapshots and reports in Postgres.
3. `report --competitor …` or `--run-id` — read markdown (URL + SEO sections).

**Risks:** Datacenter/VPN IPs often get **403** or bot walls (especially Hoka, Adidas, Brooks, Asics). A report full of `sitemap_error` means **this client was refused**, not “no market activity.” Reebok is usually the most reachable. Set `enabled: false` on brands that fail `probe` on your machine until you change network or tune config from a successful probe.

SEO changes on live sites appear when URLs are **new**, **`lastmod` changes** (not a site-wide stamp), or hit the **rotation sample**—not every URL on every run.

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

python -m wadi_scraper probe --require-enabled
python -m wadi_scraper run --competitor reebok
python -m wadi_scraper run                    # all enabled brands
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

**30+ tests** use fixtures and pure logic—no `DATABASE_URL` required for most:

| Module | Covers |
|--------|--------|
| `test_brand_certification.py` | **All five brands** — fixture ingest, no product sitemap fetch, US loc filters |
| `test_probe.py` | Probe index preview on Reebok fixture |
| `test_http_client.py` | Bot-wall HTML (captcha / challenge) detection |
| `test_sitemap.py` | Child sitemap allow/deny; product sitemap never fetched |
| `test_sitemap_encoding.py` | Gzip and Brotli sitemap bodies |
| `test_sitemap_error.py` | All sitemap 403 → `sitemap_error` |
| `test_normalize.py` | URL normalization |
| `test_diff.py` | Baseline, add/remove, bulk lastmod |
| `test_tiers.py` | Tier A/B/C classification |
| `test_fetch_queue.py` | Cap at 50, Tier C excluded from queue and diff lists |
| `test_extract.py` | HTML field extraction and change pairing |
| `test_report.py` | Markdown for baseline and sitemap errors |
| `test_snapshot_number.py` | Per-brand snapshot numbering |
| `test_serve_api.py` | Report UI read APIs, including the guide |
| `test_serve_jobs.py` | Start-crawl job lifecycle (one crawl at a time) |

Fixtures live under `tests/fixtures/<brand>/` (sanitized XML shaped like each platform).

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
config/competitors.yaml          # Five brands (all enabled; turn off after a failed probe)
config/competitors_demo.yaml     # Local proof competitor
docs/how-this-project-works.md   # Plain-English guide (UI “How this works” tab)
sql/                             # Postgres migrations
src/wadi_scraper/                # Package (sitemap, diff, fetch, report, jobs, CLI)
src/wadi_scraper/ui/             # Report viewer HTML
tests/                           # Unit + e2e proof tests
tests/fixtures/                  # Per-brand sitemap certification XML
demo/                            # Local demo HTTP server
scripts/prove_scraper_e2e.py     # Manual full HTTP proof
```

---

## Sign-off checklist (before sharing reports with Nike)

On the **same Mac/network** you will use for production runs:

- [ ] `python -m wadi_scraper probe --require-enabled` — each **enabled** brand: Probe OK, index 200, ≥1 allowed child, no product sitemap in **deny** list that was HTTP-fetched
- [ ] `run` for each enabled brand — status `ok` or `partial`, **>0** stored URLs (not all `sitemap_error`)
- [ ] Second manual run after a few days — report shows sensible **days since last snapshot** and URL/SEO sections where data exists
- [ ] Brands that fail probe remain `enabled: false` in `config/competitors.yaml`

Plan reference: `.cursor/plans/competitor_sitemap_tracker_ad29f2be.plan.md`.
