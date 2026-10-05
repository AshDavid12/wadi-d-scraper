# What this project is, in plain English

This tool watches five US footwear sites for Nike: **Reebok, Hoka, Adidas, Brooks, and Asics**. Nike’s own site is never crawled.

Someone starts a run by hand. The tool asks each site for its public sitemap (the index of pages the site already publishes for search engines), keeps the marketing URLs, and compares that list with the last successful run. It then opens a small number of those pages and notes a few on-page fields: the title, the short description, the main heading, the canonical link, and the robots tag.

The result is a report: which campaign, blog, and collection URLs showed up or disappeared, and whether those page fields changed. History lives in a cloud database (Neon Postgres). The raw sitemap files and HTML are read in memory and thrown away. Nothing is scheduled. If you do not run it, nothing happens.

```text
public sitemap  →  filtered URL list  →  saved snapshot
                         ↓
              compare with last good run
                         ↓
         open up to 50 pages  →  note title / description / heading changes
                         ↓
                      markdown report
```

## What a run actually collects

| It keeps | It leaves out |
|---|---|
| US marketing pages, blogs, and collections | Product catalogs. Product sitemaps are never requested. |
| A before/after list of those URLs | Cart, checkout, account, and search URLs |
| Title, meta description, H1, canonical, robots tag | Prices, sizes, stock, reviews, images, or a product database |
| The gap since the last good snapshot, in days | A live feed. The gap can be days or weeks. |

URLs are sorted into three buckets:

- **Tier A and B** are the marketing URLs worth opening (sales, new arrivals, and similar pages).
- **Tier C** is a pile of hash-style collection links. They are counted, and they are not listed one by one or opened.

The first good run for a brand is a baseline. Later runs only mean something when you compare them with that history.

## Limits that are on purpose

These are design choices so a person on a laptop can run a polite check, not a full copy of five websites.

- **By hand only.** There is no timer and no server that crawls overnight.
- **50 pages per brand per run.** About 10 of those are a rotating sample of older URLs. The rest are new URLs or URLs whose sitemap “last modified” date actually changed. A site-wide stamp on every URL is ignored, because that usually means the site regenerated the file, not that every page was edited.
- **The report lists at most 100 added URLs and 100 removed URLs.** Extra ones are a count, not a dump.
- **Static HTML only.** The tool reads the page as the server first sends it. Text that appears only after JavaScript runs in a browser is invisible to it.
- **US pages only.** Other countries’ URLs are filtered out from the sitemap.
- **A brand stays off until a probe succeeds** on the same computer and the same network you will use for the real run. `probe` checks that the sitemap answers and that at least one allowed child sitemap is visible. It does not download those children.
- **One blocked brand does not stop the others**, but an empty error report is not “nothing changed in the market.” It means this run never saw the sitemap.

On this Mac, only Reebok answers. A probe on 5 Oct 2026 got a real Reebok sitemap (HTTP 200, 12 allowed child sitemaps) and a full run (88 pages, 23 blogs, 4,579 collections). Hoka, Adidas, Brooks, and Asics are turned off in config because the same network refuses them. Hoka’s sitemap index and Brooks’ sitemap index returned HTTP 403. Asics sometimes returns a captcha page for both `robots.txt` and the sitemap. Trying another ordinary network is not a fix that has worked here.

## Limits that are the other company’s wall

The interesting failures are not bugs in this repo. The other company decided, on their edge network, that this request does not look like a normal shopper.

What people call a “firewall” here is usually **bot management** sitting in front of the website (often Akamai or a similar service, sometimes a captcha page). It is not a firewall on Nike’s laptop, and it is not a setting in `competitors.yaml`.

A typical refusal looks like this:

1. `robots.txt` returns HTTP 200. The site is happy to tell a stranger where the sitemap is.
2. The sitemap URL, or a page URL, returns **403**, **406**, or **429**, with a captcha or “access denied” page instead of XML or HTML.
3. The tool records that as a bot wall and stops. It does not try to solve the captcha, change its identity, or hammer the URL again. The report status becomes `sitemap_error` or `partial`. For that brand, there is no add/remove list.

A normal home or office connection is not enough for these four. The wall is scoring the **client**, not only the building the Wi‑Fi is in.

- Reebok’s Shopify sitemap will hand XML to a simple HTTP request that looks roughly like a browser. That is why this laptop can track Reebok.
- Hoka, Adidas, Brooks, and Asics put a bot check in front of the sitemap. This tool sends one browser-like User-Agent and normal Accept headers. It does not run JavaScript, keep cookies from a real visit, or complete a captcha. Their check wants those things, so the answer is 403 or a challenge page even when the request comes from a regular network. Hoka is the clearest case: `robots.txt` can be HTTP 200 while `sitemap_index_all.xml` is HTTP 403.
- A datacenter or VPN address is blocked even more often. Moving off one is still not what made Reebok work and the others fail. The split is the site’s protection, measured from this machine.

A `sitemap_error` report means **this client was refused**. It does not mean the competitor published nothing.

The tool’s own message on that failure is explicit: there is no bypass built in. Those four brands stay disabled. Reebok is the brand this project can actually report on from here.

## If this were a large project

A larger version still wants the same public facts: which US marketing URLs exist, and what the title and headings say. Getting those facts at scale is a sourcing problem. The walls above are the sites’ own rules about automated traffic. Routes that stay inside those rules are the ones that hold up.

**1. Ask for the data, or buy it from someone who is allowed to have it.**  
Brand partner programs, licensed feeds, and companies that already sell public web data are the stable version of this project. You pay or sign a contract, and the 403 stops being your problem. This is the option that still works when bot walls get stricter.

**2. Do not plan on “just use a normal network” for Hoka, Adidas, Brooks, or Asics.**  
That idea is already tested on this laptop, and it failed. Reebok works. The other four return a bot wall. More offices on the same kind of connection would keep hitting the same check, because the check is rejecting this kind of program, not this particular Wi‑Fi.

**3. A real browser is the technical step these walls are asking for, and it is a different product.**  
The 403 pages say, in effect, “run our JavaScript” or “pass a captcha.” A full browser can do the first of those and can read text that static HTML never contains. It still stops when the site demands a captcha or decides the session is automated. Building that means a new fetcher, not a setting in this scraper, and the site’s terms often still forbid automated collection of public pages. This repo does not include that fetcher.

**4. Buy the collection from a company that already operates at that scale.**  
Web-data vendors run their own browser fleets and contracts. A large Nike monitor would subscribe to a feed of marketing-URL and on-page changes for these brands, then keep this project’s diff and report. The wall stays their operational problem. You still only store the marketing fields this tool already keeps: URLs, titles, descriptions, headings. Product catalogs stay out.

**5. Leave a blocked brand out of the brief.**  
Rotating identities, solving captchas, or imitating thousands of shoppers fights a control the site put there on purpose. It breaks when the vendor updates the check, and it can violate the site’s terms or the law. This codebase does not do that. While a probe is red, the honest line in the Nike report is “we cannot see this brand from here.” Reebok can be briefed. Hoka, Adidas, Brooks, and Asics cannot, until the data arrives through a licensed feed or a browser-based collector built as its own project.

## What you can trust in a report

Trust a section when the run status is `ok` or `partial`, the probe on that same network was clean, and the URL counts are above zero. Read “days since last snapshot” before you read a quiet diff: a long gap is a long gap, not a quiet market.

Do not brief Nike on a brand whose latest run is `sitemap_error`. That page is a record of the wall, not of the competitor.
