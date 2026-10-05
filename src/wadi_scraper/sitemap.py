from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

from wadi_scraper.config import CompetitorConfig
from wadi_scraper.filters import classify_page_type, should_drop_loc
from wadi_scraper.normalize import normalize_url


class FetchFn(Protocol):
    def __call__(self, url: str) -> tuple[int, bytes, str]: ...


@dataclass
class LocEntry:
    url: str
    page_type: str
    lastmod: datetime | None


@dataclass
class IngestResult:
    entries: list[LocEntry] = field(default_factory=list)
    skipped_sitemap_links: list[str] = field(default_factory=list)
    denied_sitemap_links: list[str] = field(default_factory=list)
    requested_urls: list[str] = field(default_factory=list)
    sitemap_failures: list[tuple[str, int]] = field(default_factory=list)
    sitemap_successes: int = 0
    pages_count: int = 0
    blogs_count: int = 0
    collections_count: int = 0
    other_count: int = 0
    dropped_junk: int = 0


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_lastmod(text: str | None) -> datetime | None:
    if not text or not text.strip():
        return None
    text = text.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None


def _decompress_body(url: str, body: bytes, content_type: str) -> bytes:
    if url.rstrip("/").endswith(".gz") or "gzip" in content_type.lower():
        return gzip.decompress(body)
    return body


def _matches_any(url: str, patterns: list[str]) -> bool:
    return any(pat in url for pat in patterns)


def sitemap_child_decision(url: str, competitor: CompetitorConfig) -> str:
    if _matches_any(url, competitor.deny_sitemap_patterns):
        return "deny"
    if competitor.allow_sitemap_patterns:
        if _matches_any(url, competitor.allow_sitemap_patterns):
            return "allow"
        return "skip"
    return "allow"


def discover_sitemap_seeds(
    competitor: CompetitorConfig,
    fetch: FetchFn,
    requested: list[str],
) -> list[str]:
    seeds = list(competitor.sitemap_seeds)
    if not competitor.hosts:
        return seeds
    host = competitor.hosts[0]
    robots_url = f"https://{host}/robots.txt"
    requested.append(robots_url)
    try:
        status, body, _ = fetch(robots_url)
    except httpx.HTTPError:
        return seeds
    if status != 200:
        return seeds
    text = body.decode("utf-8", errors="replace")
    from_robots: list[str] = []
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            loc = line.split(":", 1)[1].strip()
            if loc:
                from_robots.append(loc)
    return from_robots if from_robots else seeds


def _parse_sitemap_xml(xml_bytes: bytes) -> tuple[list[str], list[tuple[str, str | None]]]:
    root = ET.fromstring(xml_bytes)
    tag = _local(root.tag)
    child_locs: list[str] = []
    page_locs: list[tuple[str, str | None]] = []

    if tag == "sitemapindex":
        for sitemap_el in root.iter():
            if _local(sitemap_el.tag) != "sitemap":
                continue
            loc_text = None
            for child in sitemap_el:
                if _local(child.tag) == "loc" and child.text:
                    loc_text = child.text.strip()
            if loc_text:
                child_locs.append(loc_text)
        return child_locs, page_locs

    if tag == "urlset":
        for url_el in root.iter():
            if _local(url_el.tag) != "url":
                continue
            loc_text = None
            lastmod_text = None
            for child in url_el:
                if _local(child.tag) == "loc" and child.text:
                    loc_text = child.text.strip()
                elif _local(child.tag) == "lastmod" and child.text:
                    lastmod_text = child.text.strip()
            if loc_text:
                page_locs.append((loc_text, lastmod_text))
        return child_locs, page_locs

    return child_locs, page_locs


def _fetch_xml(
    url: str,
    fetch: FetchFn,
    requested: list[str],
    failures: list[tuple[str, int]],
    success_counter: list[int],
) -> bytes | None:
    requested.append(url)
    status, body, content_type = fetch(url)
    if status != 200:
        failures.append((url, status))
        return None
    success_counter[0] += 1
    return _decompress_body(url, body, content_type)


def _walk_sitemap(
    url: str,
    competitor: CompetitorConfig,
    fetch: FetchFn,
    requested: list[str],
    skipped: list[str],
    denied: list[str],
    seen_sitemaps: set[str],
    failures: list[tuple[str, int]],
    success_counter: list[int],
) -> list[tuple[str, str | None]]:
    if url in seen_sitemaps:
        return []
    seen_sitemaps.add(url)

    xml_bytes = _fetch_xml(url, fetch, requested, failures, success_counter)
    if xml_bytes is None:
        return []

    child_locs, page_locs = _parse_sitemap_xml(xml_bytes)
    out = list(page_locs)
    for child in child_locs:
        decision = sitemap_child_decision(child, competitor)
        if decision == "deny":
            denied.append(child)
            continue
        if decision == "skip":
            skipped.append(child)
            continue
        out.extend(
            _walk_sitemap(
                child,
                competitor,
                fetch,
                requested,
                skipped,
                denied,
                seen_sitemaps,
                failures,
                success_counter,
            )
        )
    return out


def ingest_run_status(ingest: IngestResult) -> str:
    """ok | sitemap_error | partial"""
    if not ingest.entries and (ingest.sitemap_failures or ingest.sitemap_successes == 0):
        return "sitemap_error"
    if ingest.sitemap_failures and ingest.entries:
        return "partial"
    if not ingest.entries:
        return "sitemap_error"
    return "ok"


def ingest_competitor_sitemap(
    competitor: CompetitorConfig,
    fetch: FetchFn | None = None,
) -> IngestResult:
    requested: list[str] = []
    skipped: list[str] = []
    denied: list[str] = []
    seen: set[str] = set()
    failures: list[tuple[str, int]] = []
    success_counter = [0]
    result = IngestResult()

    def default_fetch(url: str) -> tuple[int, bytes, str]:
        with httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "wadi-scraper/0.1 (+https://github.com/wadi-d-scraper)"},
        ) as client:
            resp = client.get(url)
            ct = resp.headers.get("content-type", "")
            return resp.status_code, resp.content, ct

    fetch_fn: FetchFn = fetch or default_fetch
    seeds = discover_sitemap_seeds(competitor, fetch_fn, requested)
    raw_locs: list[tuple[str, str | None]] = []
    for seed in seeds:
        if _matches_any(seed, competitor.deny_sitemap_patterns):
            denied.append(seed)
            continue
        raw_locs.extend(
            _walk_sitemap(
                seed,
                competitor,
                fetch_fn,
                requested,
                skipped,
                denied,
                seen,
                failures,
                success_counter,
            )
        )

    seen_urls: set[str] = set()
    for loc, lastmod_raw in raw_locs:
        normalized = normalize_url(loc, competitor.normalize)
        if should_drop_loc(normalized, competitor):
            result.dropped_junk += 1
            continue
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        page_type = classify_page_type(urlparse(normalized).path or "/")
        lastmod = _parse_lastmod(lastmod_raw)
        result.entries.append(
            LocEntry(url=normalized, page_type=page_type, lastmod=lastmod)
        )
        if page_type == "page":
            result.pages_count += 1
        elif page_type == "blog":
            result.blogs_count += 1
        elif page_type == "collection":
            result.collections_count += 1
        else:
            result.other_count += 1

    result.skipped_sitemap_links = skipped
    result.denied_sitemap_links = denied
    result.requested_urls = requested
    result.sitemap_failures = failures
    result.sitemap_successes = success_counter[0]
    return result


def any_product_sitemap_requested(requested: list[str]) -> list[str]:
    return [u for u in requested if re.search(r"sitemap_products_", u, re.I)]
