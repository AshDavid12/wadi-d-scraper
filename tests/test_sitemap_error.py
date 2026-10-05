from wadi_scraper.config import load_config
from wadi_scraper.sitemap import ingest_competitor_sitemap, ingest_run_status


def test_all_sitemap_fetches_403_is_sitemap_error():
    cfg = load_config().get("reebok")

    def fetch(url: str) -> tuple[int, bytes, str]:
        if "robots.txt" in url or "sitemap" in url:
            return 403, b"blocked", "text/html"
        return 404, b"", "text/plain"

    result = ingest_competitor_sitemap(cfg, fetch=fetch)
    assert result.entries == []
    assert ingest_run_status(result) == "sitemap_error"
    assert result.sitemap_failures
