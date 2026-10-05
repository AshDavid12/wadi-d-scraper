CREATE TABLE IF NOT EXISTS runs (
  id BIGSERIAL PRIMARY KEY,
  competitor_id TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  error_message TEXT,
  pages_count INT NOT NULL DEFAULT 0,
  blogs_count INT NOT NULL DEFAULT 0,
  collections_count INT NOT NULL DEFAULT 0,
  other_count INT NOT NULL DEFAULT 0,
  skipped_sitemap_links JSONB NOT NULL DEFAULT '[]'::jsonb,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS runs_competitor_started_idx
  ON runs (competitor_id, started_at DESC);

CREATE TABLE IF NOT EXISTS url_observations (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
  competitor_id TEXT NOT NULL,
  url TEXT NOT NULL,
  page_type TEXT NOT NULL,
  lastmod TIMESTAMPTZ,
  UNIQUE (run_id, url)
);

CREATE INDEX IF NOT EXISTS url_observations_run_id_idx ON url_observations (run_id);
