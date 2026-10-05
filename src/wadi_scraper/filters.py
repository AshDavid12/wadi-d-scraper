from __future__ import annotations

from urllib.parse import urlparse

from wadi_scraper.config import CompetitorConfig


def classify_page_type(path: str, platform: str | None = None) -> str:
    lower = (path or "/").lower()
    if path.startswith("/pages/") or path == "/pages":
        return "page"
    if path.startswith("/blogs/") or path == "/blogs":
        return "blog"
    if path.startswith("/collections/") or path == "/collections":
        return "collection"
    if platform == "glass":
        if "/blog" in lower:
            return "blog"
        if lower.startswith("/us/"):
            if "/product/" in lower or lower.endswith(".html") and "product" in lower:
                return "other"
            return "collection"
    if platform == "sfcc":
        if "/blog" in lower or "/stories/" in lower:
            return "blog"
        if "/product/" in lower or lower.endswith("-product.xml"):
            return "other"
        if "/en/us/" in lower or lower.startswith("/en/us"):
            return "collection"
    if platform == "custom":
        if "/blog/" in lower:
            return "blog"
        if lower.startswith("/en_us/"):
            if "/product/" in lower or "/p/" in lower:
                return "other"
            return "collection"
        if lower.startswith("/us/en-us/"):
            if "/product/" in lower:
                return "other"
            if "/blog/" in lower:
                return "blog"
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
    if competitor.allow_loc_path_prefixes:
        if not any(
            lower_path.startswith(p.lower()) for p in competitor.allow_loc_path_prefixes
        ):
            return True
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
