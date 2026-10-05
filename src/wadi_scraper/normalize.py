from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from wadi_scraper.config import NormalizeConfig


def normalize_url(url: str, cfg: NormalizeConfig) -> str:
    parsed = urlparse(url.strip())
    scheme = cfg.scheme or parsed.scheme or "https"
    netloc = parsed.netloc
    if cfg.lowercase_host:
        netloc = netloc.lower()
    path = parsed.path or ""
    if cfg.strip_trailing_slash and path != "/":
        path = path.rstrip("/")
    fragment = "" if cfg.strip_fragment else parsed.fragment
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, fragment))
