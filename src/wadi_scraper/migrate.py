from __future__ import annotations

from pathlib import Path

import psycopg


def migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "sql"


def apply_migrations(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          filename TEXT PRIMARY KEY,
          applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    for path in sorted(migrations_dir().glob("*.sql")):
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE filename = %s",
            (path.name,),
        ).fetchone()
        if row:
            continue
        sql = path.read_text()
        conn.execute(sql)
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (%s)",
            (path.name,),
        )
    conn.commit()
