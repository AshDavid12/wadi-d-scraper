CREATE TABLE IF NOT EXISTS page_snapshots (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
  competitor_id TEXT NOT NULL,
  url TEXT NOT NULL,
  final_url TEXT,
  canonical_url TEXT,
  http_status INT,
  title TEXT NOT NULL DEFAULT '',
  meta_description TEXT NOT NULL DEFAULT '',
  h1s JSONB NOT NULL DEFAULT '[]'::jsonb,
  meta_robots TEXT NOT NULL DEFAULT '',
  low_confidence BOOLEAN NOT NULL DEFAULT FALSE,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (run_id, url)
);

CREATE INDEX IF NOT EXISTS page_snapshots_competitor_url_idx
  ON page_snapshots (competitor_id, url, fetched_at DESC);
