from pathlib import Path

from wadi_scraper.config import load_config
from wadi_scraper.sitemap import (
    any_product_sitemap_requested,
    ingest_competitor_sitemap,
    sitemap_child_decision,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reebok"


def _fixture_map() -> dict[str, bytes]:
    return {
        "https://www.reebok.com/robots.txt": (
            b"User-agent: *\nSitemap: https://www.reebok.com/sitemap_index.xml\n"
        ),
        "https://www.reebok.com/sitemap_index.xml": (
            FIXTURES / "sitemap_index.xml"
        ).read_bytes(),
        "https://www.reebok.com/sitemap_pages_1.xml?from=1&to=2": (
            FIXTURES / "sitemap_pages_1.xml"
        ).read_bytes(),
    }


def test_sitemap_child_decision():
    cfg = load_config().get("reebok")
    assert sitemap_child_decision("https://x/sitemap_products_1.xml", cfg) == "deny"
    assert (
        sitemap_child_decision("https://x/sitemap_agentic_discovery.xml", cfg) == "deny"
    )
    assert sitemap_child_decision("https://x/sitemap_pages_1.xml", cfg) == "allow"
    assert sitemap_child_decision("https://x/sitemap_unknown_future.xml", cfg) == "skip"


def test_ingest_never_fetches_product_sitemap():
    cfg = load_config().get("reebok")
    fixtures = _fixture_map()
    requested: list[str] = []

    def fetch(url: str) -> tuple[int, bytes, str]:
        requested.append(url)
        if url not in fixtures:
            return 404, b"", "text/plain"
        return 200, fixtures[url], "application/xml"

    result = ingest_competitor_sitemap(cfg, fetch=fetch)

    assert any_product_sitemap_requested(result.requested_urls) == []
    assert not any("sitemap_products_" in u for u in result.requested_urls)
    assert "https://www.reebok.com/sitemap_pages_1.xml?from=1&to=2" in result.requested_urls

    urls = {e.url for e in result.entries}
    assert "https://www.reebok.com/pages/about-reebok" in urls
    assert "https://www.reebok.com/blogs/news/collab-story" in urls
    assert "https://www.reebok.com/collections/sale" in urls
    assert "https://www.reebok.com/products/shoe-123" not in urls
    assert all("/cart" not in u for u in urls)

    assert result.pages_count == 2
    assert result.blogs_count == 1
    assert result.collections_count == 1
    assert len(result.skipped_sitemap_links) == 1
    assert len(result.denied_sitemap_links) == 2
