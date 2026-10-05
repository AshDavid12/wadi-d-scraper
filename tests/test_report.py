from wadi_scraper.diff import InventoryDiff
from wadi_scraper.report import CompetitorReportBlock, SeoReportSection, render_markdown


def test_markdown_sitemap_error_is_explicit():
    block = CompetitorReportBlock(
        competitor_id="adidas",
        competitor_name="Adidas",
        run_id=9,
        status="sitemap_error",
        error_message="Sitemap fetch failed: https://www.adidas.com/sitemap.xml → HTTP 403",
        started_at=None,
        finished_at=None,
        pages_count=0,
        blogs_count=0,
        collections_count=0,
        other_count=0,
        skipped_sitemap_links=[],
        denied_sitemap_links=[],
        sitemap_failures=[("https://www.adidas.com/sitemap.xml", 403)],
        diff=InventoryDiff(baseline=False, days_since_previous=None, previous_run_id=None),
        seo=SeoReportSection(),
    )
    md = render_markdown("Nike", [block], generated_at_utc="2026-10-05 08:00:00 UTC")
    assert "**Generated (UTC):** 2026-10-05 08:00:00 UTC" in md
    assert "**Status:** `sitemap_error`" in md
    assert "no URL add/remove data" in md
    assert "HTTP 403" in md


def test_markdown_baseline():
    block = CompetitorReportBlock(
        competitor_id="reebok",
        competitor_name="Reebok",
        run_id=1,
        status="ok",
        error_message=None,
        started_at=None,
        finished_at=None,
        pages_count=10,
        blogs_count=2,
        collections_count=100,
        other_count=0,
        skipped_sitemap_links=[],
        denied_sitemap_links=["https://x/sitemap_products_1.xml"],
        sitemap_failures=[],
        diff=InventoryDiff(baseline=True, days_since_previous=None, previous_run_id=None),
        seo=SeoReportSection(fetched=10, candidates=120),
    )
    md = render_markdown("Nike", [block], generated_at_utc="2026-10-05 08:00:00 UTC")
    assert "**Generated (UTC):**" in md
    assert "Baseline run" in md
