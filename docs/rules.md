# Rules — non-negotiable

## Safety & secrets
- Secrets live only in `.env` (local), `/etc/econdb/econdb.env` (VPS) or GitHub Secrets.
  Never commit, print, echo or log them. `.env.example` lists variable names only.
- Ask for explicit approval before: any destructive SQL (DROP, TRUNCATE, DELETE, or UPDATE on
  `core`/`raw` tables), `git push --force`, installing system software, opening firewall ports,
  or changing anything on the VPS.
- The database is never exposed to the public internet. Access is local, SSH tunnel or private VPN.
- Only ever touch the `econdb` database and its roles. Other databases on the same server
  (e.g. `rohingya_as_wb` locally) belong to other projects — never read, alter or drop them.
- Never ask the owner to paste passwords into the chat; they go into `.env` directly.

## VPS (shared with a live production app — Bharat Laws)
- Never touch Bharat Laws files or services, MySQL, nginx, aaPanel or `/www` on the VPS.
- On the VPS, PostgreSQL 16 listens on `localhost:5432` only; the pipeline runs as a dedicated
  non-root `econdb` Linux user with memory limits (systemd `MemoryMax`).
- No reboot, OS upgrade or firewall change without the owner's explicit approval and a planned
  maintenance window; firewall changes go through aaPanel or with the owner's approval.

## Data integrity
- `core.observation` is append-only. A changed value is a NEW row with a new `vintage_at`.
- Base year is part of a series' identity. Never splice or mix base years. Linked series are
  computed only from official factors in `meta.linking_factor` and stored as separate series.
- Store numbers exactly as published (`numeric`, never float). Units, scale (crore/lakh/million)
  and currency live in `meta.series`; never rescale values on the way in.
- Record the estimate stage (advance / provisional / first revised / final) whenever given.
- Periods: `period_start`, `period_end`, `freq` (D/W/M/Q/A). Financial year = Apr–Mar;
  FY quarters Q1 Apr–Jun … Q4 Jan–Mar. Calendar-year series are explicitly flagged.
- Timestamps are UTC (`timestamptz`). Schedules and displays use Asia/Kolkata.
- Official aggregates beat derived ones. Derive only when no official figure exists.
- Aggregation rule per series (`meta.series.agg_rule`): index → mean; flow → sum;
  stock → end of period; market price/rate → end AND mean; ratio → recompute from parts;
  growth/inflation → recompute from the aggregated level (never average rates).
- A derived period is complete only when all its sub-periods exist; otherwise `is_partial = true`.

## Sources
- One adapter per source in `src/econdb/sources/`, same interface: fetch → normalise → validate → load.
  One failing source must never stop the others.
- Save every raw response/file (gzip) to the raw archive BEFORE parsing.
- Timeouts, retries with exponential backoff, browser-like User-Agent for government sites,
  ≥0.5 s between requests, respect robots.txt, no parallel hammering of one host.
- Paginate everything. MoSPI returns only 10 rows per page by default.
- Never scrape paid/licensed data (PMI detail, CMIE, SIAM detail, private property data).
  Headline figures from public press releases only.
- Yahoo Finance is unofficial: internal use only, and never the sole source of a key series
  when an official source exists.

## Code
- Python 3.12, type hints, `ruff` (lint + format), `pytest`. Dependencies pinned.
- Config through environment variables; identical code on Windows (local) and Linux (VPS).
  Use `pathlib`; never hard-code `D:\` or Linux paths.
- DB access with psycopg 3 (or SQLAlchemy Core). Migrations are numbered SQL files in
  `db/migrations/NNNN_description.sql`, applied by `econdb migrate`, recorded in
  `ops.schema_migrations`. Never edit an applied migration — add a new one.
- Structured JSON logs in `logs/`; every pipeline run has a `run_id`.
- Each adapter's normaliser has unit tests using saved sample responses in `tests/fixtures/`.
  Unit tests never call the network.

## Workflow
- Work phase by phase (`docs/phases.md`). At each checkpoint: summarise, show evidence
  (row counts, sample values, test results), and wait for approval.
- Non-trivial work starts in plan mode with the plan shown first.
- Commit per logical step with clear messages; push to `origin main` after checkpoint approval.
- Local shell is Windows PowerShell; VPS shell is bash. Give commands for the correct one.
- Update `docs/memory.md` when a phase finishes, a decision is made, or a source quirk is found.
