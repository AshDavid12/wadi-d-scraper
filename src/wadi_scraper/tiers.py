from __future__ import annotations

import re
from urllib.parse import urlparse

from wadi_scraper.config import TierConfig

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"

_DEFAULT_HASH = re.compile(r"-0[a-z0-9]{5,8}$", re.I)


def collection_slug(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "collections":
        return parts[1]
    return ""


def classify_url_tier(url: str, page_type: str, tier: TierConfig) -> str:
    path = (urlparse(url).path or "/").lower()

    if page_type == "collection":
        slug = collection_slug(path)
        pat = tier.tier_c_slug_pattern
        if pat and re.search(pat, slug):
            return TIER_C
        if any(k in slug for k in tier.tier_a_collection_keywords):
            return TIER_A
        return TIER_B

    if page_type == "blog":
        return TIER_A

    if page_type == "page":
        if any(d in path for d in tier.tier_page_deny_substrings):
            return TIER_B
        if any(k in path for k in tier.tier_a_page_keywords):
            return TIER_A
        return TIER_B

    return TIER_B


def is_fetchable_tier(tier: str) -> bool:
    return tier in (TIER_A, TIER_B)
