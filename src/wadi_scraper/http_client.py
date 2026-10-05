from __future__ import annotations

import httpx

# Consumer-browser profile; some competitors allow robots.txt but block bot User-Agents on sitemaps.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def default_headers() -> dict[str, str]:
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }


def new_client(**kwargs: object) -> httpx.Client:
    headers = dict(default_headers())
    extra = kwargs.pop("headers", None)
    if isinstance(extra, dict):
        headers.update(extra)
    return httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers=headers,
        **kwargs,
    )


def looks_like_bot_wall(status: int, body: bytes) -> bool:
    if status not in (403, 406, 429):
        return False
    sample = body[:2000].lower()
    markers = (
        b"access denied",
        b"captcha",
        b"captcha-delivery",
        b"please enable js",
        b"#cmsg",
        b"geo.captcha-delivery.com",
        b"security issue was automatically identified",
        b"akamai",
        b"edgesuite.net",
    )
    return any(m in sample for m in markers)
