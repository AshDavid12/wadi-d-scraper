from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from wadi_scraper.config import CompetitorConfig
from wadi_scraper.http_client import looks_like_bot_wall, new_client
from wadi_scraper.sitemap import (
    FetchFn,
    discover_sitemap_seeds,
    looks_like_sitemap_xml,
    prepare_sitemap_bytes,
    preview_index_children,
    sitemap_child_decision,
)


@dataclass
class ProbeResult:
    competitor_id: str
    robots_url: str | None = None
    robots_status: int | None = None
    robots_sitemap_lines: list[str] = field(default_factory=list)
    index_urls: list[str] = field(default_factory=list)
    index_status: dict[str, int] = field(default_factory=dict)
    index_children: list[tuple[str, str, str]] = field(default_factory=list)
    index_bot_wall: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.errors:
            return False
        if not any(status == 200 for status in self.index_status.values()):
            return False
        allowed = [c for c in self.index_children if c[1] == "allow"]
        return bool(allowed)


def _default_fetch(url: str) -> tuple[int, bytes, str]:
    with new_client() as client:
        resp = client.get(url)
        ct = resp.headers.get("content-type", "")
        return resp.status_code, resp.content, ct


def probe_competitor(
    competitor: CompetitorConfig,
    fetch: FetchFn | None = None,
) -> ProbeResult:
    fetch_fn = fetch or _default_fetch
    out = ProbeResult(competitor_id=competitor.id)

    if competitor.hosts:
        host = competitor.hosts[0]
        robots_url = f"https://{host}/robots.txt"
        out.robots_url = robots_url
        try:
            status, body, _ = fetch_fn(robots_url)
            out.robots_status = status
            if status == 200:
                text = body.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        out.robots_sitemap_lines.append(line.split(":", 1)[1].strip())
            elif looks_like_bot_wall(status, body):
                out.index_bot_wall = True
                out.errors.append(
                    f"{robots_url}: HTTP {status} — bot wall (not plain robots.txt)"
                )
        except httpx.HTTPError as exc:
            out.errors.append(f"robots.txt: {exc}")

    requested: list[str] = []
    seeds = discover_sitemap_seeds(competitor, fetch_fn, requested)
    out.index_urls = list(seeds)

    for seed in seeds:
        if sitemap_child_decision(seed, competitor) == "deny":
            out.index_children.append((seed, "deny", seed))
            continue
        try:
            status, body, ct = fetch_fn(seed)
        except httpx.HTTPError as exc:
            out.errors.append(f"{seed}: {exc}")
            continue
        body = prepare_sitemap_bytes(seed, body, ct)
        out.index_status[seed] = status
        if status != 200:
            msg = f"{seed}: HTTP {status}"
            if looks_like_bot_wall(status, body):
                out.index_bot_wall = True
                robots_note = (
                    "robots.txt also blocked on this run."
                    if out.robots_status and out.robots_status != 200
                    else "robots.txt may still be 200 on other runs/networks."
                )
                msg += (
                    " — bot wall (captcha/challenge HTML, not sitemap XML). "
                    f"{robots_note} No bypass in this tool; keep "
                    f"{competitor.id} disabled or use another network."
                )
            out.errors.append(msg)
            continue
        if not looks_like_sitemap_xml(body):
            hint = " (bot wall or HTML)" if looks_like_bot_wall(status, body) else ""
            out.errors.append(f"{seed}: response is not sitemap XML{hint}")
            if looks_like_bot_wall(status, body):
                out.index_bot_wall = True
            continue
        try:
            children = preview_index_children(body, competitor)
        except ValueError as exc:
            out.errors.append(f"{seed}: {exc}")
            continue
        for child, decision in children:
            out.index_children.append((child, decision, seed))

    if not out.index_children:
        if out.index_bot_wall:
            out.errors.append(
                "Sitemap ingest unavailable from this client: index never returned XML."
            )
        else:
            out.errors.append("No sitemap index children parsed (check seeds / network)")
    elif not any(d == "allow" for _, d, _ in out.index_children):
        out.errors.append("No allowed child sitemaps in index preview")

    denied_fetches = [u for u in requested if sitemap_child_decision(u, competitor) == "deny"]
    if denied_fetches:
        out.errors.append(
            f"Denied sitemap URL was requested (bug): {denied_fetches[0]}"
        )

    return out


def format_probe_report(result: ProbeResult) -> str:
    lines = [f"## Probe — {result.competitor_id}", ""]
    if result.robots_url:
        lines.append(f"- robots.txt: `{result.robots_url}` → HTTP {result.robots_status}")
    if result.robots_sitemap_lines:
        lines.append(f"- Sitemap lines in robots: {len(result.robots_sitemap_lines)}")
        if len(result.robots_sitemap_lines) <= 5:
            for s in result.robots_sitemap_lines:
                lines.append(f"  - {s}")
        else:
            lines.append(f"  - (first) {result.robots_sitemap_lines[0]}")
            lines.append(f"  - … {len(result.robots_sitemap_lines) - 1} more")
    lines.append(f"- Index seed(s) probed: {len(result.index_urls)}")
    for seed, status in result.index_status.items():
        lines.append(f"  - `{seed}` → HTTP {status}")

    by_decision: dict[str, list[str]] = {"allow": [], "deny": [], "skip": []}
    for child, decision, _ in result.index_children:
        if child in result.index_urls:
            continue
        by_decision.setdefault(decision, []).append(child)

    for decision in ("allow", "skip", "deny"):
        urls = by_decision.get(decision) or []
        lines.append(f"- Child sitemaps **{decision}**: {len(urls)}")
        for u in urls[:8]:
            lines.append(f"  - {u}")
        if len(urls) > 8:
            lines.append(f"  - … and {len(urls) - 8} more")

    if result.errors:
        lines.append("- **Issues:**")
        for e in result.errors:
            lines.append(f"  - {e}")
    lines.append(f"- **Probe OK:** {'yes' if result.ok else 'no'}")
    return "\n".join(lines)
