from wadi_scraper.config import load_config
from wadi_scraper.probe import probe_competitor

from test_brand_certification import BRAND_FIXTURES, _fetch_from_map


def test_probe_does_not_crash_on_gzip_sitemap_index():
    cfg = load_config().get("reebok")
    import gzip

    raw = gzip.compress(
        b'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        b"<sitemap><loc>https://www.reebok.com/sitemap_pages_1.xml</loc></sitemap>"
        b"</sitemapindex>"
    )

    def fetch(url: str) -> tuple[int, bytes, str]:
        if url.endswith("robots.txt"):
            return 200, b"Sitemap: https://www.reebok.com/sitemap.xml\n", "text/plain"
        return 200, raw, "application/gzip"

    result = probe_competitor(cfg, fetch=fetch)
    assert result.ok
    assert any(d == "allow" for _, d, _ in result.index_children)


def test_probe_html_200_does_not_crash():
    cfg = load_config().get("reebok")

    def fetch(url: str) -> tuple[int, bytes, str]:
        if url.endswith("robots.txt"):
            return 200, b"Sitemap: https://www.reebok.com/sitemap.xml\n", "text/plain"
        return 200, b"<html><body>blocked</body></html>", "text/html"

    result = probe_competitor(cfg, fetch=fetch)
    assert not result.ok
    assert not any("ParseError" in e for e in result.errors)


def test_probe_reebok_fixture_index_preview():
    cfg = load_config().get("reebok")
    fixtures = BRAND_FIXTURES["reebok"]()
    # Probe uses discover + fetch seeds; reebok uses robots - add robots to map
    result = probe_competitor(cfg, fetch=_fetch_from_map(fixtures))
    assert result.index_status.get("https://www.reebok.com/sitemap_index.xml") == 200
    allowed = [u for u, d, _ in result.index_children if d == "allow"]
    assert any("sitemap_pages_" in u for u in allowed)
    denied = [u for u, d, _ in result.index_children if d == "deny"]
    assert any("product" in u.lower() for u in denied)
