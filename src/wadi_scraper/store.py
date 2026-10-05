from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

from wadi_scraper.diff import UrlRow
from wadi_scraper.migrate import apply_migrations
from wadi_scraper.sitemap import IngestResult, LocEntry


@dataclass
class RunRecord:
    id: int
    competitor_id: str
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    error_message: str | None
    pages_count: int
    blogs_count: int
    collections_count: int
    other_count: int
    skipped_sitemap_links: list[str]
    meta: dict[str, Any]


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def ensure_schema(conn: psycopg.Connection) -> None:
    apply_migrations(conn)


def create_run(conn: psycopg.Connection, competitor_id: str) -> int:
    row = conn.execute(
        """
        INSERT INTO runs (competitor_id, status)
        VALUES (%s, 'running')
        RETURNING id
        """,
        (competitor_id,),
    ).fetchone()
    assert row is not None
    conn.commit()
    return int(row[0])


def _ingest_meta(ingest: IngestResult, extra: dict[str, Any] | None) -> dict[str, Any]:
    meta = {
        "denied_sitemap_links": ingest.denied_sitemap_links,
        "dropped_junk": ingest.dropped_junk,
        "requested_url_count": len(ingest.requested_urls),
        "sitemap_failures": [{"url": u, "http_status": s} for u, s in ingest.sitemap_failures],
        "sitemap_successes": ingest.sitemap_successes,
    }
    if extra:
        meta.update(extra)
    return meta


def finish_run(
    conn: psycopg.Connection,
    run_id: int,
    *,
    status: str,
    ingest: IngestResult,
    error_message: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> None:
    meta = _ingest_meta(ingest, extra_meta)
    conn.execute(
        """
        UPDATE runs SET
          finished_at = NOW(),
          status = %s,
          error_message = %s,
          pages_count = %s,
          blogs_count = %s,
          collections_count = %s,
          other_count = %s,
          skipped_sitemap_links = %s::jsonb,
          meta = %s::jsonb
        WHERE id = %s
        """,
        (
            status,
            error_message,
            ingest.pages_count,
            ingest.blogs_count,
            ingest.collections_count,
            ingest.other_count,
            json.dumps(ingest.skipped_sitemap_links),
            json.dumps(meta),
            run_id,
        ),
    )
    conn.commit()


def insert_url_observations(
    conn: psycopg.Connection,
    run_id: int,
    competitor_id: str,
    entries: list[LocEntry],
) -> None:
    if not entries:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO url_observations (run_id, competitor_id, url, page_type, lastmod)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (run_id, url) DO NOTHING
            """,
            [
                (run_id, competitor_id, e.url, e.page_type, e.lastmod)
                for e in entries
            ],
        )
    conn.commit()


def _row_to_run(row: tuple) -> RunRecord:
    skipped = row[9]
    if isinstance(skipped, str):
        skipped = json.loads(skipped)
    meta = row[10]
    if isinstance(meta, str):
        meta = json.loads(meta)
    return RunRecord(
        id=int(row[0]),
        competitor_id=row[1],
        started_at=row[2],
        finished_at=row[3],
        status=row[4],
        error_message=row[5],
        pages_count=int(row[6] or 0),
        blogs_count=int(row[7] or 0),
        collections_count=int(row[8] or 0),
        other_count=int(row[11] or 0) if len(row) > 11 else 0,
        skipped_sitemap_links=list(skipped or []),
        meta=dict(meta or {}),
    )


_RUN_SELECT = """
SELECT id, competitor_id, started_at, finished_at, status, error_message,
       pages_count, blogs_count, collections_count, skipped_sitemap_links, meta,
       other_count
FROM runs
"""


def get_run(conn: psycopg.Connection, run_id: int) -> RunRecord | None:
    row = conn.execute(_RUN_SELECT + " WHERE id = %s", (run_id,)).fetchone()
    if not row:
        return None
    return _row_to_run(row)


def get_latest_run(
    conn: psycopg.Connection, competitor_id: str | None = None
) -> RunRecord | None:
    if competitor_id:
        row = conn.execute(
            _RUN_SELECT
            + " WHERE competitor_id = %s ORDER BY id DESC LIMIT 1",
            (competitor_id,),
        ).fetchone()
    else:
        row = conn.execute(_RUN_SELECT + " ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    return _row_to_run(row)


def get_previous_successful_run(
    conn: psycopg.Connection, competitor_id: str, before_run_id: int
) -> RunRecord | None:
    row = conn.execute(
        _RUN_SELECT
        + """
        WHERE competitor_id = %s AND id < %s AND status = 'ok'
        ORDER BY id DESC LIMIT 1
        """,
        (competitor_id, before_run_id),
    ).fetchone()
    if not row:
        return None
    return _row_to_run(row)


def load_url_observations(conn: psycopg.Connection, run_id: int) -> dict[str, UrlRow]:
    rows = conn.execute(
        """
        SELECT url, page_type, lastmod FROM url_observations WHERE run_id = %s
        """,
        (run_id,),
    ).fetchall()
    out: dict[str, UrlRow] = {}
    for url, page_type, lastmod in rows:
        out[url] = UrlRow(url=url, page_type=page_type, lastmod=lastmod)
    return out


def save_report(conn: psycopg.Connection, run_id: int, report_md: str, report_json: str) -> None:
    conn.execute(
        """
        UPDATE runs SET report_md = %s, report_json = %s::jsonb WHERE id = %s
        """,
        (report_md, report_json, run_id),
    )
    conn.commit()


def insert_page_snapshot(
    conn: psycopg.Connection,
    run_id: int,
    competitor_id: str,
    fields: "PageFields",
) -> None:
    from wadi_scraper.extract import PageFields

    assert isinstance(fields, PageFields)
    conn.execute(
        """
        INSERT INTO page_snapshots (
          run_id, competitor_id, url, final_url, canonical_url, http_status,
          title, meta_description, h1s, meta_robots, low_confidence
        ) VALUES (
          %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
        )
        ON CONFLICT (run_id, url) DO UPDATE SET
          final_url = EXCLUDED.final_url,
          canonical_url = EXCLUDED.canonical_url,
          http_status = EXCLUDED.http_status,
          title = EXCLUDED.title,
          meta_description = EXCLUDED.meta_description,
          h1s = EXCLUDED.h1s,
          meta_robots = EXCLUDED.meta_robots,
          low_confidence = EXCLUDED.low_confidence,
          fetched_at = NOW()
        """,
        (
            run_id,
            competitor_id,
            fields.url,
            fields.final_url,
            fields.canonical_url,
            fields.http_status,
            fields.title,
            fields.meta_description,
            json.dumps(fields.h1s),
            fields.meta_robots,
            fields.low_confidence,
        ),
    )
    conn.commit()


def get_last_page_snapshot(
    conn: psycopg.Connection,
    competitor_id: str,
    url: str,
    *,
    before_run_id: int,
) -> tuple | None:
    return conn.execute(
        """
        SELECT url, final_url, http_status, title, meta_description, h1s,
               canonical_url, meta_robots, low_confidence
        FROM page_snapshots
        WHERE competitor_id = %s AND url = %s AND run_id < %s
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (competitor_id, url, before_run_id),
    ).fetchone()


def pick_rotation_urls(
    conn: psycopg.Connection,
    competitor_id: str,
    candidate_urls: list[str],
    limit: int,
    *,
    before_run_id: int,
) -> list[str]:
    if not candidate_urls or limit <= 0:
        return []
    rows = conn.execute(
        """
        WITH candidates AS (
          SELECT unnest(%s::text[]) AS url
        )
        SELECT c.url,
               (
                 SELECT MAX(ps.fetched_at)
                 FROM page_snapshots ps
                 WHERE ps.competitor_id = %s AND ps.url = c.url AND ps.run_id < %s
               ) AS last_fetch
        FROM candidates c
        ORDER BY last_fetch NULLS FIRST, c.url
        LIMIT %s
        """,
        (candidate_urls, competitor_id, before_run_id, limit),
    ).fetchall()
    return [r[0] for r in rows]


def get_report(conn: psycopg.Connection, run_id: int) -> tuple[str | None, dict[str, Any] | None]:
    row = conn.execute(
        "SELECT report_md, report_json FROM runs WHERE id = %s",
        (run_id,),
    ).fetchone()
    if not row:
        return None, None
    md, js = row[0], row[1]
    if isinstance(js, str):
        js = json.loads(js)
    return md, js
