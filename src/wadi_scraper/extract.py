from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape

import httpx


@dataclass
class PageFields:
    url: str
    final_url: str
    http_status: int
    title: str = ""
    meta_description: str = ""
    h1s: list[str] = field(default_factory=list)
    canonical_url: str = ""
    meta_robots: str = ""
    low_confidence: bool = False


def normalize_field(text: str) -> str:
    return " ".join(unescape(text or "").split())


def extract_from_html(url: str, final_url: str, http_status: int, html: str) -> PageFields:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = normalize_field(title_m.group(1)) if title_m else ""

    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if not desc_m:
        desc_m = re.search(
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']',
            html,
            re.I,
        )
    meta_description = normalize_field(desc_m.group(1)) if desc_m else ""

    canon_m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if not canon_m:
        canon_m = re.search(
            r'<link[^>]+href=["\']([^"\']*)["\'][^>]+rel=["\']canonical["\']',
            html,
            re.I,
        )
    canonical_url = canon_m.group(1).strip() if canon_m else ""

    robots_m = re.search(
        r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    meta_robots = normalize_field(robots_m.group(1)) if robots_m else ""

    h1s = [
        normalize_field(m.group(1))
        for m in re.finditer(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    ]
    h1s = [h for h in h1s if h]

    low_confidence = bool(title) and not h1s

    return PageFields(
        url=url,
        final_url=final_url,
        http_status=http_status,
        title=title,
        meta_description=meta_description,
        h1s=h1s,
        canonical_url=canonical_url,
        meta_robots=meta_robots,
        low_confidence=low_confidence,
    )


def fetch_page_fields(url: str, fetch_html: httpx.Client) -> PageFields:
    resp = fetch_html.get(url)
    html = resp.text if resp.content else ""
    return extract_from_html(url, str(resp.url), resp.status_code, html)
