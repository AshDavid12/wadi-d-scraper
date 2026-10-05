# How this works

Tracks five US competitors for Nike: **Reebok, Hoka, Adidas, Brooks, and Asics**. Nike is not crawled.

From this computer, only Reebok returns a sitemap. Probe and crawl still run for the other four. Those sites refuse the request, so no URL list is stored.

This version starts each run by hand, from the command line or this UI. A schedule is not included. The same pipeline can be started on a timer in a later version.

Each run reads the public sitemap, keeps US marketing URLs, compares them with the last successful snapshot, opens up to 50 pages, and writes a report. Snapshots and reports are stored in Neon Postgres. Sitemap XML and page HTML are discarded after the run.

```text
sitemap → filtered URLs → snapshot → diff → up to 50 pages → report
```

## What a run stores

| Kept | Left out |
|---|---|
| US pages, blogs, and collections | Product sitemaps and product URLs |
| Added and removed URLs since the last good snapshot | Cart, checkout, account, and search URLs |
| Title, meta description, H1, canonical, robots | Price, size, stock, reviews, images |
| Days since the last good snapshot | |

The first successful run for a brand is a baseline. Later reports compare against that history.

On Reebok, URLs are sorted before any page is opened:

- **Tier A and B.** Sales, new arrivals, and similar pages. These can be opened.
- **Tier C.** Collection URLs whose names end in a short code, such as `0acz00a`. Counted only. Not listed one by one, and not opened.

## Limits in this version

- **Start.** Manual, from the CLI or this UI. Scheduling uses the same run later; it is not built here.
- **Pages.** 50 per brand. About 10 are a rotating sample of older URLs. The rest are new URLs, or URLs whose own last-modified date changed. A stamp shared by the whole sitemap is ignored.
- **Report length.** At most 100 added URLs and 100 removed URLs are listed. The rest are a count.
- **HTML.** The first response from the server. Text added by JavaScript is not read.
- **Locale.** US URLs only.
- **Probe.** Checks that the sitemap answers and that at least one allowed child sitemap is listed. It does not download those children, and it does not change which brands are enabled.
- **Enabled brands.** All five are enabled. “Run all enabled” tries each one. A refusal is saved as `sitemap_error`, with no added or removed URLs. Set `enabled: false` to leave a brand out.
- **One failure stays with that brand.** The other brands still run.

Probe on 5 Oct 2026: Reebok returned HTTP 200, 12 allowed child sitemaps, then a full run of 88 pages, 23 blogs, and 4,579 collections. Hoka and Brooks returned HTTP 403 on the sitemap index. Asics sometimes returns a captcha page. Another ordinary network has not changed that result.

## When a site refuses

Hoka, Adidas, Brooks, and Asics put a bot check in front of the sitemap. `robots.txt` often returns HTTP 200. The sitemap then returns **403**, **406**, **429**, or a captcha page.

The tool records the refusal and stops. It does not solve captchas or retry past that check. Probe prints a bot-wall note. A crawl saves `sitemap_error`, or `partial` when some sitemap files loaded and others did not.

A `sitemap_error` report means this client was refused. Reebok’s sitemap returns XML to this client. The other four do not, from this machine. Leave them enabled to record the refusal, or set `enabled: false` to skip them.

## Reading a report

Use a section when the status is `ok` or `partial`, the probe on that network succeeded, and the URL counts are above zero. Read the days since the last snapshot before treating a quiet diff as a quiet market.

A `sitemap_error` section records the refusal.
