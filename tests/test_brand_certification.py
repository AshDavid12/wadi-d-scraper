"""Phase 4: ingest fixture sitemaps for all five brands (no live network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wadi_scraper.config import load_config
from wadi_scraper.sitemap import any_product_sitemap_requested, ingest_competitor_sitemap

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch_from_map(fixtures: dict[str, bytes]):
    def fetch(url: str) -> tuple[int, bytes, str]:
        if url not in fixtures:
            return 404, b"", "text/plain"
        return 200, fixtures[url], "application/xml"

    return fetch


def _reebok_fixtures() -> dict[str, bytes]:
    base = FIXTURES / "reebok"
    return {
        "https://www.reebok.com/robots.txt": (
            b"User-agent: *\nSitemap: https://www.reebok.com/sitemap_index.xml\n"
        ),
        "https://www.reebok.com/sitemap_index.xml": (base / "sitemap_index.xml").read_bytes(),
        "https://www.reebok.com/sitemap_pages_1.xml?from=1&to=2": (
            base / "sitemap_pages_1.xml"
        ).read_bytes(),
    }


def _hoka_fixtures() -> dict[str, bytes]:
    base = FIXTURES / "hoka"
    return {
        "https://www.hoka.com/sitemap_index_all.xml": (
            base / "sitemap_index_all.xml"
        ).read_bytes(),
        "https://www.hoka.com/sitemap_en_us_content.xml": (
            base / "sitemap_en_us_content.xml"
        ).read_bytes(),
    }


def _adidas_fixtures() -> dict[str, bytes]:
    base = FIXTURES / "adidas"
    return {
        "https://www.adidas.com/glass/sitemaps/adidas/US/en/sitemap-index.xml": (
            base / "sitemap_index.xml"
        ).read_bytes(),
        "https://www.adidas.com/glass/sitemaps/adidas/US/en/sitemaps/plp-sitemap-1.xml": (
            base / "plp-sitemap-1.xml"
        ).read_bytes(),
        "https://www.adidas.com/glass/sitemaps/adidas/US/en/sitemaps/blog-pages-sitemap.xml": (
            base / "blog-pages-sitemap.xml"
        ).read_bytes(),
    }


def _brooks_fixtures() -> dict[str, bytes]:
    base = FIXTURES / "brooks"
    return {
        "https://www.brooksrunning.com/sitemap_index.xml": (
            base / "sitemap_index.xml"
        ).read_bytes(),
        "https://www.brooksrunning.com/en_us/sitemap_categories.xml": (
            base / "sitemap_categories.xml"
        ).read_bytes(),
    }


def _asics_fixtures() -> dict[str, bytes]:
    base = FIXTURES / "asics"
    return {
        "https://www.asics.com/us/en-us/sitemap_index.xml": (
            base / "sitemap_index.xml"
        ).read_bytes(),
        "https://www.asics.com/sitemap-content_0.xml": (
            base / "sitemap-content_0.xml"
        ).read_bytes(),
    }


BRAND_FIXTURES = {
    "reebok": _reebok_fixtures,
    "hoka": _hoka_fixtures,
    "adidas": _adidas_fixtures,
    "brooks": _brooks_fixtures,
    "asics": _asics_fixtures,
}


@pytest.mark.parametrize("brand_id", list(BRAND_FIXTURES.keys()))
def test_brand_fixture_ingest_never_fetches_product_sitemaps(brand_id: str):
    app = load_config()
    competitor = app.get(brand_id)
    fixture_map = BRAND_FIXTURES[brand_id]()
    result = ingest_competitor_sitemap(competitor, fetch=_fetch_from_map(fixture_map))

    assert any_product_sitemap_requested(result.requested_urls, competitor) == []
    assert not any(
        "product" in u.lower() and "sitemap" in u.lower()
        for u in result.requested_urls
    )
    assert result.entries, f"{brand_id}: expected stored URLs"
    urls = {e.url for e in result.entries}
    assert all("/cart" not in u for u in urls)
    for bad in ("en-ca", "/de/", "/jp/ja-jp", "en_ca"):
        assert not any(bad in u for u in urls), f"{brand_id}: locale leak {bad} in {urls}"


@pytest.mark.parametrize("brand_id", list(BRAND_FIXTURES.keys()))
def test_brand_fixture_has_us_marketing_urls(brand_id: str):
    app = load_config()
    competitor = app.get(brand_id)
    result = ingest_competitor_sitemap(
        competitor, fetch=_fetch_from_map(BRAND_FIXTURES[brand_id]())
    )
    assert result.pages_count + result.collections_count + result.blogs_count + result.other_count >= 2
