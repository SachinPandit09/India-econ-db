CREATE TABLE ops.pipeline_run (
    run_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    command      text NOT NULL,
    triggered_by text NOT NULL CHECK (triggered_by IN ('manual', 'timer', 'backfill')),
    host         text,
    git_sha      text,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    status       text NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'ok', 'partial', 'failed'))
);

CREATE TABLE ops.source_run (
    source_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        bigint NOT NULL REFERENCES ops.pipeline_run,
    source_id     text NOT NULL REFERENCES meta.source,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'ok', 'failed', 'skipped')),
    rows_new      integer NOT NULL DEFAULT 0,
    rows_revised  integer NOT NULL DEFAULT 0,
    latest_period date,
    error         text
);
CREATE INDEX source_run_source_started_idx ON ops.source_run (source_id, started_at DESC);

CREATE TABLE ops.quality_issue (
    issue_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_run_id bigint REFERENCES ops.source_run,
    series_id     text REFERENCES meta.series,
    period_start  date,
    check_name    text NOT NULL,
    severity      text NOT NULL CHECK (severity IN ('info', 'warn', 'error')),
    detail        jsonb,
    detected_at   timestamptz NOT NULL DEFAULT now(),
    resolved_at   timestamptz
);

CREATE TABLE ops.alert (
    alert_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind         text NOT NULL CHECK (kind IN ('failure', 'late', 'quality')),
    source_id    text REFERENCES meta.source,
    series_id    text REFERENCES meta.series,
    message      text NOT NULL,
    github_issue integer,
    opened_at    timestamptz NOT NULL DEFAULT now(),
    closed_at    timestamptz
);
