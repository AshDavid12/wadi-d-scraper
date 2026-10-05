from wadi_scraper.config import load_config
from wadi_scraper.diff import InventoryDiff, UrlRow, diff_inventory
from wadi_scraper.fetch_queue import build_fetch_queue
from wadi_scraper.tiers import classify_url_tier


def test_tier_c_never_in_fetch_queue():
    cfg = load_config().get("reebok")
    hash_url = "https://www.reebok.com/collections/foo-0acz00a"
    sale_url = "https://www.reebok.com/collections/sale"
    current = {
        hash_url: UrlRow(hash_url, "collection", None),
        sale_url: UrlRow(sale_url, "collection", None),
    }
    diff = InventoryDiff(baseline=True, days_since_previous=None, previous_run_id=None)
    queue, total = build_fetch_queue(cfg, current, None, diff, rotate_urls=[])
    assert hash_url not in queue
    assert sale_url in queue
    assert total == 1


def test_fetch_cap_at_50():
    cfg = load_config().get("reebok")
    current = {
        f"https://www.reebok.com/blogs/news/post-{i}": UrlRow(
            f"https://www.reebok.com/blogs/news/post-{i}", "blog", None
        )
        for i in range(80)
    }
    diff = InventoryDiff(baseline=True, days_since_previous=None, previous_run_id=None)
    queue, total = build_fetch_queue(cfg, current, None, diff, rotate_urls=[])
    assert len(queue) == 50
    assert total == 80


def test_tier_c_excluded_from_diff_list():
    cfg = load_config().get("reebok")
    hash_url = "https://www.reebok.com/collections/foo-0acz00a"
    sale_url = "https://www.reebok.com/collections/sale"

    def tier_fn(url, page_type):
        return classify_url_tier(url, page_type, cfg.tiers)

    prev = {sale_url: UrlRow(sale_url, "collection", None)}
    curr = {
        sale_url: UrlRow(sale_url, "collection", None),
        hash_url: UrlRow(hash_url, "collection", None),
    }
    diff = diff_inventory(prev, curr, tier_fn=tier_fn)
    assert hash_url not in diff.added
    assert diff.tier_c_added_count == 1
