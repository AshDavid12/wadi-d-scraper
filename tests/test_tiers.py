from wadi_scraper.config import load_config
from wadi_scraper.tiers import TIER_A, TIER_B, TIER_C, classify_url_tier


def test_tier_c_hash_collection():
    cfg = load_config().get("reebok")
    url = "https://www.reebok.com/collections/womens-bright-colored-running-shoes-0acz00a"
    assert classify_url_tier(url, "collection", cfg.tiers) == TIER_C


def test_tier_a_sale_collection():
    cfg = load_config().get("reebok")
    url = "https://www.reebok.com/collections/sale"
    assert classify_url_tier(url, "collection", cfg.tiers) == TIER_A


def test_tier_a_blog():
    cfg = load_config().get("reebok")
    url = "https://www.reebok.com/blogs/news/story"
    assert classify_url_tier(url, "blog", cfg.tiers) == TIER_A


def test_tier_page_deny_is_b():
    cfg = load_config().get("reebok")
    url = "https://www.reebok.com/pages/privacy-policy"
    assert classify_url_tier(url, "page", cfg.tiers) == TIER_B
