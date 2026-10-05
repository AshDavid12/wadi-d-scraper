from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wadi_scraper.extract import PageFields, normalize_field


@dataclass
class FieldChange:
    url: str
    field: str
    before: str
    after: str
    low_confidence: bool = False


@dataclass
class SeoDiffResult:
    changes: list[FieldChange] = field(default_factory=list)


def _h1s_str(h1s: list[str]) -> str:
    return " | ".join(h1s)


def diff_page_fields(before: PageFields | None, after: PageFields) -> list[FieldChange]:
    if before is None:
        return []
    changes: list[FieldChange] = []
    pairs = [
        ("title", before.title, after.title),
        ("meta_description", before.meta_description, after.meta_description),
        ("h1", _h1s_str(before.h1s), _h1s_str(after.h1s)),
        ("canonical", before.canonical_url, after.canonical_url),
        ("meta_robots", before.meta_robots, after.meta_robots),
    ]
    for field_name, old, new in pairs:
        old_n = normalize_field(old)
        new_n = normalize_field(new)
        if old_n != new_n:
            changes.append(
                FieldChange(
                    url=after.url,
                    field=field_name,
                    before=old_n,
                    after=new_n,
                    low_confidence=after.low_confidence,
                )
            )
    return changes


def seo_diff_to_dict(result: SeoDiffResult) -> dict[str, Any]:
    return {
        "changes": [
            {
                "url": c.url,
                "field": c.field,
                "before": c.before,
                "after": c.after,
                "low_confidence": c.low_confidence,
            }
            for c in result.changes
        ]
    }
