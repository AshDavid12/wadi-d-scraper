from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class NormalizeConfig:
    scheme: str = "https"
    strip_fragment: bool = True
    lowercase_host: bool = True
    strip_trailing_slash: bool = False


@dataclass
class FetchConfig:
    max_pages: int = 50
    rotate_sample: int = 10
    delay_seconds: float = 0.5


@dataclass
class TierConfig:
    tier_c_slug_pattern: str = r"-0[a-z0-9]{5,8}$"
    tier_a_collection_keywords: list[str] = field(
        default_factory=lambda: ["sale", "new-arrival", "new-arrivals"]
    )
    tier_a_page_keywords: list[str] = field(
        default_factory=lambda: ["sale", "new-arrival", "about", "membership", "promo"]
    )
    tier_page_deny_substrings: list[str] = field(
        default_factory=lambda: [
            "size-guide",
            "privacy",
            "cookie",
            "terms",
            "accessibility",
            "opt-out",
            "shipping",
            "returns",
        ]
    )


@dataclass
class CompetitorConfig:
    id: str
    name: str
    enabled: bool
    hosts: list[str] = field(default_factory=list)
    platform: str | None = None
    html_mode: str = "static"
    fetch: FetchConfig = field(default_factory=FetchConfig)
    tiers: TierConfig = field(default_factory=TierConfig)
    sitemap_seeds: list[str] = field(default_factory=list)
    allow_sitemap_patterns: list[str] = field(default_factory=list)
    deny_sitemap_patterns: list[str] = field(default_factory=list)
    deny_loc_path_prefixes: list[str] = field(default_factory=list)
    deny_loc_substrings: list[str] = field(default_factory=list)
    drop_loc_path_prefixes: list[str] = field(default_factory=list)
    allow_loc_path_prefixes: list[str] = field(default_factory=list)
    deny_sitemap_substrings: list[str] = field(default_factory=list)
    sitemap_discovery: str = "robots_then_seeds"
    normalize: NormalizeConfig = field(default_factory=NormalizeConfig)


@dataclass
class AppConfig:
    client: str
    competitors: list[CompetitorConfig]

    def get(self, competitor_id: str) -> CompetitorConfig:
        for c in self.competitors:
            if c.id == competitor_id:
                return c
        raise KeyError(f"Unknown competitor: {competitor_id}")

    def enabled(self) -> list[CompetitorConfig]:
        return [c for c in self.competitors if c.enabled]


def _normalize_block(raw: dict[str, Any] | None) -> NormalizeConfig:
    if not raw:
        return NormalizeConfig()
    return NormalizeConfig(
        scheme=raw.get("scheme", "https"),
        strip_fragment=raw.get("strip_fragment", True),
        lowercase_host=raw.get("lowercase_host", True),
        strip_trailing_slash=raw.get("strip_trailing_slash", False),
    )


def load_config(path: Path | None = None) -> AppConfig:
    if path is None:
        env_path = os.environ.get("WADI_CONFIG")
        if env_path:
            path = Path(env_path)
        else:
            path = Path(__file__).resolve().parents[2] / "config" / "competitors.yaml"
    data = yaml.safe_load(path.read_text())
    competitors = []
    for raw in data.get("competitors", []):
        competitors.append(
            CompetitorConfig(
                id=raw["id"],
                name=raw["name"],
                enabled=bool(raw.get("enabled", False)),
                hosts=list(raw.get("hosts") or []),
                platform=raw.get("platform"),
                sitemap_seeds=list(raw.get("sitemap_seeds") or []),
                allow_sitemap_patterns=list(raw.get("allow_sitemap_patterns") or []),
                deny_sitemap_patterns=list(raw.get("deny_sitemap_patterns") or []),
                deny_loc_path_prefixes=list(raw.get("deny_loc_path_prefixes") or []),
                deny_loc_substrings=list(raw.get("deny_loc_substrings") or []),
                drop_loc_path_prefixes=list(raw.get("drop_loc_path_prefixes") or []),
                allow_loc_path_prefixes=list(raw.get("allow_loc_path_prefixes") or []),
                deny_sitemap_substrings=list(raw.get("deny_sitemap_substrings") or []),
                sitemap_discovery=str(
                    raw.get("sitemap_discovery", "robots_then_seeds")
                ),
                normalize=_normalize_block(raw.get("normalize")),
                html_mode=str(raw.get("html_mode", "static")),
                fetch=_fetch_block(raw.get("fetch")),
                tiers=_tier_block(raw.get("tiers")),
            )
        )
    return AppConfig(client=data.get("client", ""), competitors=competitors)


def _fetch_block(raw: dict[str, Any] | None) -> FetchConfig:
    if not raw:
        return FetchConfig()
    return FetchConfig(
        max_pages=int(raw.get("max_pages", 50)),
        rotate_sample=int(raw.get("rotate_sample", 10)),
        delay_seconds=float(raw.get("delay_seconds", 0.5)),
    )


def _tier_block(raw: dict[str, Any] | None) -> TierConfig:
    if not raw:
        return TierConfig()
    base = TierConfig()
    return TierConfig(
        tier_c_slug_pattern=str(raw.get("tier_c_slug_pattern", base.tier_c_slug_pattern)),
        tier_a_collection_keywords=list(
            raw.get("tier_a_collection_keywords") or base.tier_a_collection_keywords
        ),
        tier_a_page_keywords=list(
            raw.get("tier_a_page_keywords") or base.tier_a_page_keywords
        ),
        tier_page_deny_substrings=list(
            raw.get("tier_page_deny_substrings") or base.tier_page_deny_substrings
        ),
    )
