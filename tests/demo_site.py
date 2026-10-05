"""Deterministic fake competitor site (v1 / v2) for end-to-end proof tests."""

from __future__ import annotations

from wadi_scraper.extract import PageFields, extract_from_html

BASE = "http://127.0.0.1:8765"

PAGES_V1 = [
    f"{BASE}/pages/promo-hub",
    f"{BASE}/pages/about",
    f"{BASE}/collections/sale",
    f"{BASE}/blogs/news/launch",
]

PAGES_V2 = [
    f"{BASE}/pages/promo-hub",
    f"{BASE}/pages/new-campaign",
    f"{BASE}/collections/sale",
    f"{BASE}/blogs/news/launch",
]


def sitemap_index_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{BASE}/sitemap_pages_1.xml</loc></sitemap>
</sitemapindex>"""


def _lastmod_for_url(url: str, version: int) -> str:
    """Simulate CMS updates: v2 bumps lastmod only where HTML/SEO changed."""
    if url.endswith("/pages/promo-hub") or url.endswith("/collections/sale"):
        return "2026-02-01" if version == 1 else "2026-03-15"
    if url.endswith("/pages/about"):
        return "2026-01-10"
    if url.endswith("/pages/new-campaign"):
        return "2026-03-15"
    return "2026-01-20"


def sitemap_pages_xml(version: int) -> str:
    urls = PAGES_V1 if version == 1 else PAGES_V2
    parts: list[str] = []
    for u in urls:
        lm = _lastmod_for_url(u, version)
        parts.append(f"<url><loc>{u}</loc><lastmod>{lm}</lastmod></url>")
    body = "".join(parts)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


def demo_page_urls(version: int) -> list[str]:
    return list(PAGES_V1 if version == 1 else PAGES_V2)


def index_html(version: int) -> str:
    links = demo_page_urls(version)
    items = "\n".join(
        f'<li><a href="{path.replace(BASE, "")}">{path.replace(BASE, "")}</a></li>'
        for path in links
    )
    other = f"""
<li><a href="/sitemap.xml">/sitemap.xml</a></li>
<li><a href="/sitemap_pages_1.xml">/sitemap_pages_1.xml</a></li>
<li><a href="/robots.txt">/robots.txt</a></li>"""
    switch = (
        "Stop this server and run: <code>DEMO_VERSION=2 python demo/local_server.py</code>"
        if version == 1
        else "Stop this server and run: <code>DEMO_VERSION=1 python demo/local_server.py</code>"
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8" />
<title>Demo competitor site v{version}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; }}
  .badge {{ display: inline-block; background: #111; color: #fff; padding: 0.2rem 0.5rem; border-radius: 4px; }}
  code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; }}
</style>
</head><body>
<p><span class="badge">Site version {version}</span></p>
<h1>Demo Local Site</h1>
<p>Fake Shopify-style pages used to prove the scraper. Compare v1 vs v2 after switching the server.</p>
<h2>Pages in sitemap</h2>
<ul>
{items}
{other}
</ul>
<p>{switch}</p>
</body></html>"""


def page_html(url: str, version: int) -> str:
    if url.endswith("/pages/promo-hub"):
        title = "Winter Promo | Demo Brand" if version == 1 else "Spring Mega Sale | Demo Brand"
        h1 = "Winter Promo" if version == 1 else "Spring Mega Sale"
        desc = "Save 10% on classics." if version == 1 else "Save 30% — limited time."
    elif url.endswith("/pages/about"):
        title = "About Demo Brand"
        h1 = "About us"
        desc = "Our story."
    elif url.endswith("/pages/new-campaign"):
        title = "New Campaign 2026 | Demo Brand"
        h1 = "New Campaign"
        desc = "Just launched."
    elif url.endswith("/collections/sale"):
        title = "Sale Collection | Demo Brand" if version == 1 else "Sale — Up to 30% Off | Demo Brand"
        h1 = "Sale"
        desc = "Deals on shoes."
    elif url.endswith("/blogs/news/launch"):
        title = "Launch Blog | Demo Brand"
        h1 = "Launch"
        desc = "Collab news."
    else:
        title = "Unknown"
        h1 = "Unknown"
        desc = ""

    canon = url
    return f"""<!DOCTYPE html>
<html><head>
<title>{title}</title>
<meta name="description" content="{desc}" />
<link rel="canonical" href="{canon}" />
<meta name="robots" content="index,follow" />
</head><body><h1>{h1}</h1></body></html>"""


def page_fields(url: str, version: int) -> PageFields:
    html = page_html(url, version)
    return extract_from_html(url, url, 200, html)


def demo_fetch(url: str, version: int) -> tuple[int, bytes, str]:
    if url.endswith("/robots.txt"):
        body = f"Sitemap: {BASE}/sitemap.xml\n".encode()
        return 200, body, "text/plain"
    if url.endswith("/sitemap.xml"):
        return 200, sitemap_index_xml().encode(), "application/xml"
    if url.endswith("/sitemap_pages_1.xml"):
        return 200, sitemap_pages_xml(version).encode(), "application/xml"
    return 404, b"", "text/plain"
