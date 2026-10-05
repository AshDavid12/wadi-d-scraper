from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from wadi_scraper.config import AppConfig
from wadi_scraper.runner import run_ingest
from wadi_scraper.store import competitor_snapshot_number, connect, ensure_schema


@dataclass
class Job:
    job_id: str
    status: str = "queued"
    lines: list[str] = field(default_factory=list)
    run_ids: list[int] = field(default_factory=list)
    error: str | None = None


class JobManager:
    """In-memory job queue for local UI (single user, one active crawl)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._active_job_id: str | None = None

    def has_active_job(self) -> bool:
        with self._lock:
            return self._active_job_id is not None

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(
        self,
        database_url: str,
        app: AppConfig,
        competitor_ids: list[str],
        *,
        run_fn: Callable[..., tuple[int, Any, str]] | None = None,
    ) -> str | None:
        """Return job_id, or None if another job is already running."""
        with self._lock:
            if self._active_job_id is not None:
                return None
            job_id = uuid.uuid4().hex[:12]
            job = Job(job_id=job_id)
            self._jobs[job_id] = job
            self._active_job_id = job_id

        ingest_fn = run_fn or run_ingest
        thread = threading.Thread(
            target=self._execute,
            args=(job_id, database_url, app, competitor_ids, ingest_fn),
            daemon=True,
        )
        thread.start()
        return job_id

    def _log(self, job: Job, line: str) -> None:
        job.lines.append(line)

    def _execute(
        self,
        job_id: str,
        database_url: str,
        app: AppConfig,
        competitor_ids: list[str],
        ingest_fn: Callable[..., tuple[int, Any, str]],
    ) -> None:
        job = self._jobs[job_id]
        job.status = "running"
        try:
            self._log(job, f"Job {job_id}: {len(competitor_ids)} brand(s) queued")
            with connect(database_url) as conn:
                ensure_schema(conn)
                for cid in competitor_ids:
                    self._log(job, f"Fetching sitemap for {cid}…")
                    try:
                        competitor = app.get(cid)
                    except KeyError:
                        self._log(job, f"Unknown competitor: {cid}")
                        continue
                    if not competitor.enabled:
                        self._log(job, f"Skipped {cid} (disabled in config)")
                        continue
                    try:
                        run_id, ingest, run_status = ingest_fn(conn, app, competitor)
                    except Exception as exc:
                        self._log(job, f"{cid} failed: {exc}")
                        continue
                    job.run_ids.append(run_id)
                    snap = competitor_snapshot_number(conn, cid, run_id)
                    self._log(
                        job,
                        f"{cid}: snapshot #{snap} · status={run_status} "
                        f"pages={ingest.pages_count} blogs={ingest.blogs_count} "
                        f"collections={ingest.collections_count}",
                    )
            job.status = "done"
            self._log(job, "Finished.")
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            self._log(job, f"Job failed: {exc}")
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def to_dict(self, job: Job) -> dict:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "lines": list(job.lines),
            "run_ids": list(job.run_ids),
            "error": job.error,
        }


# Shared registry for the local serve process
default_job_manager = JobManager()
