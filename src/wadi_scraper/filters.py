from __future__ import annotations

from urllib.parse import urlparse

from wadi_scraper.config import CompetitorConfig


def classify_page_type(path: str) -> str:
    if path.startswith("/pages/") or path == "/pages":
        return "page"
    if path.startswith("/blogs/") or path == "/blogs":
        return "blog"
    if path.startswith("/collections/") or path == "/collections":
        return "collection"
    return "other"


def host_allowed(url: str, competitor: CompetitorConfig) -> bool:
    host = urlparse(url).netloc.lower()
    allowed = {h.lower() for h in competitor.hosts}
    return host in allowed if allowed else True


def should_drop_loc(url: str, competitor: CompetitorConfig) -> bool:
    if not host_allowed(url, competitor):
        return True
    parsed = urlparse(url)
    path = parsed.path or "/"
    lower_path = path.lower()
    for prefix in competitor.drop_loc_path_prefixes:
        if lower_path.startswith(prefix.lower()):
            return True
    for prefix in competitor.deny_loc_path_prefixes:
        if lower_path.startswith(prefix.lower()):
            return True
    full = url.lower()
    for sub in competitor.deny_loc_substrings:
        if sub.lower() in full:
            return True
    return False
