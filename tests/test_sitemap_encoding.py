import gzip

from wadi_scraper.sitemap import looks_like_sitemap_xml, prepare_sitemap_bytes

XML = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://example.com/a.xml</loc></sitemap></sitemapindex>"""


def test_prepare_decompresses_brotli_when_needed():
    import brotli

    compressed = brotli.compress(XML)
    out = prepare_sitemap_bytes("https://x/sitemap.xml", compressed, "application/xml")
    assert looks_like_sitemap_xml(out)
    assert b"sitemapindex" in out


def test_prepare_decompresses_gzip():
    compressed = gzip.compress(XML)
    out = prepare_sitemap_bytes("https://x/sitemap.xml.gz", compressed, "application/gzip")
    assert looks_like_sitemap_xml(out)
