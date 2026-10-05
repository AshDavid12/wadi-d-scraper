from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from wadi_scraper.diff import InventoryDiff, diff_to_dict
from wadi_scraper.seo_diff import FieldChange, SeoDiffResult, seo_diff_to_dict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_datetime_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def report_generated_at_utc() -> tuple[str, str]:
    """Human-readable label and ISO-8601 Z for JSON."""
    now = utc_now()
    label = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    iso = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return label, iso


@dataclass
class SeoReportSection:
    candidates: int = 0
    fetched: int = 0
    field_changes: list[FieldChange] = field(default_factory=list)
    html_mode: str = "static"


@dataclass
class CompetitorReportBlock:
    competitor_id: str
    competitor_name: str
    run_id: int
    status: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    pages_count: int
    blogs_count: int
    collections_count: int
    other_count: int
    skipped_sitemap_links: list[str]
    denied_sitemap_links: list[str]
    sitemap_failures: list[tuple[str, int]]
    diff: InventoryDiff
    seo: SeoReportSection


def build_report_payload(
    client: str,
    blocks: list[CompetitorReportBlock],
    *,
    generated_at_utc: str,
    generated_at_utc_iso: str,
) -> dict[str, Any]:
    return {
        "client": client,
        "generated_at_utc": generated_at_utc_iso,
        "generated_at_utc_display": generated_at_utc,
        "competitors": [
            {
                "id": b.competitor_id,
                "name": b.competitor_name,
                "run_id": b.run_id,
                "status": b.status,
                "error_message": b.error_message,
                "started_at_utc": format_datetime_utc(b.started_at),
                "finished_at_utc": format_datetime_utc(b.finished_at),
                "counts": {
                    "pages": b.pages_count,
                    "blogs": b.blogs_count,
                    "collections": b.collections_count,
                    "other": b.other_count,
                },
                "skipped_sitemap_links": b.skipped_sitemap_links,
                "denied_sitemap_links": b.denied_sitemap_links,
                "sitemap_failures": [
                    {"url": u, "http_status": s} for u, s in b.sitemap_failures
                ],
                "inventory_diff": diff_to_dict(b.diff),
                "seo": {
                    "html_mode": b.seo.html_mode,
                    "fetched": b.seo.fetched,
                    "candidates": b.seo.candidates,
                    **seo_diff_to_dict(SeoDiffResult(changes=b.seo.field_changes)),
                },
            }
            for b in blocks
        ],
    }


def render_markdown(
    client: str,
    blocks: list[CompetitorReportBlock],
    *,
    generated_at_utc: str,
) -> str:
    lines: list[str] = [
        f"# Competitor sitemap report — {client}",
        "",
        f"**Generated (UTC):** {generated_at_utc}",
        "",
    ]
    for b in blocks:
        lines.append(f"## {b.competitor_name} ({b.competitor_id})")
        lines.append("")
        lines.append(f"**Status:** `{b.status}` · **Run ID:** {b.run_id}")
        if b.error_message:
            lines.append(f"**Error:** {b.error_message}")
        if b.diff.days_since_previous is not None:
            lines.append(
                f"**Days since last successful snapshot:** {b.diff.days_since_previous}"
            )
        lines.append("")
        if b.status == "sitemap_error":
            lines.append(
                "_Sitemap could not be loaded — no URL add/remove data for this run._"
            )
            if b.sitemap_failures:
                lines.append("")
                lines.append("Failed requests:")
                for url, code in b.sitemap_failures[:20]:
                    lines.append(f"- `{url}` → HTTP {code}")
            lines.append("")
            continue

        lines.append("### Inventory counts")
        lines.append(
            f"- Pages: {b.pages_count} · Blogs: {b.blogs_count} · "
            f"Collections: {b.collections_count} · Other: {b.other_count}"
        )
        if b.skipped_sitemap_links:
            lines.append(
                f"- Skipped sitemap children: {len(b.skipped_sitemap_links)}"
            )
        if b.denied_sitemap_links:
            lines.append(
                f"- Denied sitemap children (not fetched): {len(b.denied_sitemap_links)}"
            )
        lines.append("")

        d = b.diff
        if d.baseline:
            lines.append("### URL inventory changes")
            lines.append("_Baseline run — no prior snapshot to compare._")
        else:
            lines.append("### URL inventory changes")
            listed_added = len(d.added) + d.added_remainder
            listed_removed = len(d.removed) + d.removed_remainder
            total_added = listed_added + d.tier_c_added_count
            total_removed = listed_removed + d.tier_c_removed_count
            lines.append(
                f"- Added: {total_added} "
                f"(listed {listed_added}, tier-C merchandising {d.tier_c_added_count})"
            )
            for url in d.added:
                lines.append(f"  - {url}")
            if d.added_remainder:
                lines.append(f"  - … and {d.added_remainder} more")

            lines.append(
                f"- Removed: {total_removed} "
                f"(listed {listed_removed}, tier-C merchandising {d.tier_c_removed_count})"
            )
            for url in d.removed:
                lines.append(f"  - {url}")
            if d.removed_remainder:
                lines.append(f"  - … and {d.removed_remainder} more")

            if d.bulk_lastmod_ignored:
                bl = d.bulk_lastmod_ignored
                lines.append(
                    f"- Bulk lastmod ignored: {bl.url_count} URLs sharing `{bl.timestamp}` "
                    "(likely sitemap rebuild)"
                )
            elif d.lastmod_changed_count:
                lines.append(f"- Selective lastmod changes: {d.lastmod_changed_count}")

        lines.append("")
        seo = b.seo
        if b.status != "sitemap_error":
            lines.append("### Confirmed SEO field changes")
            lines.append(
                f"- HTML fetch: **{seo.fetched} of {seo.candidates}** "
                f"(cap 50, mode `{seo.html_mode}`)"
            )
            if not seo.field_changes:
                lines.append("- No title, meta description, H1, canonical, or robots changes detected.")
            else:
                for change in seo.field_changes[:50]:
                    conf = " _(low confidence — empty H1, likely JS)_" if change.low_confidence else ""
                    lines.append(f"- `{change.url}` · **{change.field}**{conf}")
                    lines.append(f"  - before: {change.before or '(empty)'}")
                    lines.append(f"  - after: {change.after or '(empty)'}")
                if len(seo.field_changes) > 50:
                    lines.append(f"- … and {len(seo.field_changes) - 50} more field changes")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def serialize_report(client: str, blocks: list[CompetitorReportBlock]) -> tuple[str, str]:
    generated_label, generated_iso = report_generated_at_utc()
    payload = build_report_payload(
        client,
        blocks,
        generated_at_utc=generated_label,
        generated_at_utc_iso=generated_iso,
    )
    md = render_markdown(client, blocks, generated_at_utc=generated_label)
    return md, json.dumps(payload, indent=2)
