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

Reebok (Shopify) is usually the one that answers. Hoka, Adidas, Brooks, and Asics often refuse the sitemap even when `robots.txt` itself returns a normal page.

## Limits that are the other company’s wall

The interesting failures are not bugs in this repo. The other company decided, on their edge network, that this request does not look like a normal shopper.

What people call a “firewall” here is usually **bot management** sitting in front of the website (often Akamai or a similar service, sometimes a captcha page). It is not a firewall on Nike’s laptop, and it is not a setting in `competitors.yaml`.

A typical refusal looks like this:

1. `robots.txt` returns HTTP 200. The site is happy to tell a stranger where the sitemap is.
2. The sitemap URL, or a page URL, returns **403**, **406**, or **429**, with a captcha or “access denied” page instead of XML or HTML.
3. The tool records that as a bot wall and stops. It does not try to solve the captcha, change its identity, or hammer the URL again. The report status becomes `sitemap_error` or `partial`. For that brand, there is no add/remove list.

Why a home or office Wi‑Fi often works, and a cloud server often does not:

- These services score **who is asking**. A datacenter, a VPN, or a continuous script looks different from a person in a browser on a residential or office line.
- They also score **how the ask is made**. This tool sends one browser-like User-Agent and normal Accept headers, then waits half a second between page fetches. It does not run JavaScript, so it cannot pass a check that says “please enable JavaScript” or complete an interactive captcha.
- They can allow the cheap file (`robots.txt`) and block the valuable one (the sitemap index). Hoka is the documented case: robots can be 200 while the index is 403. That is the wall working as designed.

So a report full of `sitemap_error` means **this network was refused**. It does not mean the competitor published nothing.

The tool’s own message on that failure is explicit: there is no bypass built in. Leave that brand disabled, or run again from a network where `probe` already succeeded.

## If this were a large project

A larger version still wants the same public facts: which US marketing URLs exist, and what the title and headings say. Getting those facts at scale is a sourcing problem. The walls above are the sites’ own rules about automated traffic. Routes that stay inside those rules are the ones that hold up.

**1. Ask for the data, or buy it from someone who is allowed to have it.**  
Brand partner programs, licensed feeds, and companies that already sell public web data are the stable version of this project. You pay or sign a contract, and the 403 stops being your problem. This is the option that still works when bot walls get stricter.

**2. Keep the crawl small and run it from a normal network.**  
That is what this repo already does. A person starts it on a Mac at home or in the office, on the same kind of connection a shopper uses. Five brands, 50 pages, half a second apart, only when someone asks. Many bot walls allow that and block a server in a data center doing the same job all day. Scaling this pattern means more *occasional* runs from real networks, not one machine requesting everything.

**3. Render the page in a real browser.**  
Some blocks are only “this client did not run JavaScript.” A browser (headless Chrome and similar) can see text that static HTML misses, and can pass a simple script check. It is slower, heavier, and still fails when the wall wants a captcha, a trusted IP, or a logged-in shopper. It also does not change the site’s terms of use. Those terms often forbid automated collection even when the pages are public.

**4. Spread polite requests across many normal connections.**  
A large monitoring product sometimes collects from several office or home networks, each doing a small job like this one, instead of one cloud IP asking for every sitemap. The limit moves from “one laptop” to “how much automated traffic each site will tolerate from ordinary connections.” Rate limits, captchas, and terms of use still apply on every one of those connections.

**5. Treat a bypass of the wall as out of scope.**  
Slipping past Akamai, rotating identities, solving captchas, or imitating thousands of browsers is a different product: it fights the control the site put there on purpose. It breaks as soon as the vendor updates the check, and it can violate the site’s terms or the law depending on how it is done. This codebase does not do that, and a larger Nike report should not depend on it. When `probe` is red, the honest output is “we could not see this brand from here,” plus one of the options above: another network, a licensed feed, or leave the brand disabled.

## What you can trust in a report

Trust a section when the run status is `ok` or `partial`, the probe on that same network was clean, and the URL counts are above zero. Read “days since last snapshot” before you read a quiet diff: a long gap is a long gap, not a quiet market.

Do not brief Nike on a brand whose latest run is `sitemap_error`. That page is a record of the wall, not of the competitor.
