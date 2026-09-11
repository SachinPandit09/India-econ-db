# Architecture

## 1. Overview
```mermaid
flowchart LR
  subgraph Sources
    A["MoSPI API<br/>incl. RBI datasets"]
    B["data.gov.in"]
    C["Yahoo Finance"]
    D["Downloads: RBI DBIE, OEA, CGA,<br/>AMFI, FBIL, PPAC, Grid-India"]
    E["Scrapers / PDFs"]
  end
  S["Scheduler<br/>local: manual · VPS: systemd timer"] --> R["econdb runner"]
  A & B & C & D & E --> R
  R --> RAW[("Raw archive<br/>gzip files")]
  R --> PG[("PostgreSQL<br/>meta · raw · core · derived · ops")]
  PG --> DER["Derived jobs<br/>aggregates, changes, linked series"]
  DER --> PG
  PG --> PUB["Sheets publisher"] --> GS["Google Sheets tracker"]
  R --> MON["Monitoring<br/>freshness, quality"] --> GH["GitHub Issue / e-mail alert"]
  PG --> BK["Nightly backup"] --> OFF[("Off-site copy")]
```

## 2. Environments
| | Local (build & test) | Production (VPS) |
|---|---|---|
| OS / shell | Windows / PowerShell | Linux / bash |
| PostgreSQL | 16.14 native Windows service, localhost:5432 | 16 (PGDG repo) on the VPS, listening on localhost only |
| Code | `D:\India-econ-db` | `/opt/econdb` (git clone, `git pull` to deploy) |
| Config | `.env` | `/etc/econdb/econdb.env` (root-readable only) |
| Raw archive | `D:\India-econ-db\data\raw` (git-ignored) | `/var/lib/econdb/raw` |
| Scheduler | run by hand / Windows Task Scheduler (optional) | systemd timer every 30 min → `econdb run --due`, as non-root user `econdb` with systemd `MemoryMax` |
| Access | direct | SSH on port 7576 (keys only after hardening; 443 belongs to nginx); DB via SSH tunnel or Tailscale (set up in Phase 7) |

Moving local → VPS: `pg_dump -Fc` locally → `pg_restore` on the VPS (or re-run backfills from the raw archive).

### VPS host (shared — verified Sep 2026)
- Host IT Smart, data centre Gujarat, India (AS138246 Netclues). Ubuntu 22.04.5 LTS, 2 vCPU,
  7.8 GB RAM, **no swap**, 97 GB disk (65 GB free).
- **Shared with a live production app, Bharat Laws — hands off** (`docs/rules.md`):
  `bharatlaws-backend` (Flask/Gunicorn on 127.0.0.1:5000), nginx (80/443/888), MySQL (3306, not
  reachable externally), aaPanel/BT-Panel (`/www`, port 12844, publicly reachable), Acronis backup
  agents, sendmail.
- Firewall: ufw + aaPanel ipset, default deny. Publicly open: 7576 (SSH), 80, 443, 12844, 888,
  20/21/39000–40000 (FTP, nothing listening), 22 (unused). econdb adds no public ports.

## 3. Repository layout
```
India-econ-db/
├── CLAUDE.md
├── docs/            PRD, architecture, rules, phases, design, memory, reference/*.xlsx
├── db/migrations/   0001_schemas.sql, 0002_meta.sql, ...
├── src/econdb/
│   ├── cli.py            migrate | run | backfill | derive | publish | check
│   ├── config.py         env-var settings
│   ├── db.py             connection, upsert-if-changed, run logging
│   ├── periods.py        FY / quarter / week helpers
│   ├── archive.py        raw archive read/write
│   ├── quality.py        validation rules
│   ├── sources/          base.py, mospi.py, datagovin.py, yahoo.py, rbi_dbie.py, ...
│   ├── derive/           aggregate.py, changes.py, linking.py
│   ├── publish/          sheets.py (layout, groups, formulas, incremental writes)
│   └── monitor/          freshness.py, alerts.py
├── deploy/          systemd units, backup script, VPS setup notes
├── tests/           unit tests + fixtures (saved sample responses)
├── explore/         exploration scripts (reference only)
└── .env.example
```

## 4. Database design (PostgreSQL)
Schemas: `meta` (definitions) · `raw` (large source-shaped tables) · `core` (canonical observations)
· `derived` (computed) · `ops` (runs, alerts, migrations). DDL: `db/migrations/0001…0006`,
applied by `econdb migrate`; catalogue and layout loaded by `econdb seed`.

```mermaid
erDiagram
  source ||--o{ series : publishes
  catalogue |o--o{ series : "indicator family"
  series ||--o{ core_observation : "append-only values"
  series ||--o{ derived_observation : "aggregates, changes, links"
  sheet ||--o{ sheet_column : "columns"
  series |o--o{ sheet_column : "shown in"
  pipeline_run ||--o{ source_run : "one per source"
  source ||--o{ source_run : "runs"
  source_run ||--o{ core_observation : "loaded by"
  series |o--o{ quality_issue : "flagged"
  source |o--o{ alert : "raised for"
```

### meta
- `meta.source` — source_id, name, tier (T1/T1b/T2/T3/T4), base_url, adapter, schedule (cron, Asia/Kolkata),
  expected_lag_days, active, notes.
- `meta.catalogue` — 1:1 mirror of the CATALOGUE sheet of the indicator catalogue (206 families: theme,
  priority, verification, decision, …); `meta.series.catalogue_id` points here.
- `meta.series` — **series_id** (grammar below), source_id, catalogue_id, family, name, dataset,
  dimensions (jsonb), unit, scale, currency, price_basis (current/constant), seasonal_adj,
  freq (D/W/M/Q/A/O), period_basis (FY Apr–Mar · CY · AY Jul–Jun · NULL = explicit survey periods),
  base_year, agg_rule (mean/sum/end/end_mean/recompute/none), derivation (jsonb; NULL = published by the
  source, else e.g. linked-series inputs), source_params (jsonb: API parameters or ticker), active, notes.
  CHECKs: series_id pattern, last token = freq, first token = family.
- `meta.linking_factor` — family, scope, old_base, new_base, factor (NULL until an official notice),
  source_ref, published_on. A reseed never overwrites a filled factor.
- `meta.release_calendar` — source_id, dataset, series_id (NULL = whole dataset), reference_period, expected_on.
- `meta.sheet` — the layout's CONTENTS sheet as rows (sheet_code, sheet_name, position, category, title…).
- `meta.sheet_column` — sheet_code, column_no (physical column), block_title, column_label,
  series_id (NULL = formula column, or source not built yet), agg (series freq → sheet freq),
  transform (yoy_pct / stage), calc_kind (pct / bps / diff), calc_lag, calc_ref_column (yellow formula
  columns). Drives the Sheets publisher; the column → series map is `src/econdb/series_map.py`.

### series_id grammar
`<family>.<base>.<geo>.<subject…>.<measure>.<freq>` — lowercase `[a-z0-9_]`, dot-separated.
- base: `b2024`, `b2011_12` (published base) · `l2024` (linked to that base) · omitted when no base year.
- geo: `in` All-India · `in_xx` states/UTs (ISO 3166-2:IN, e.g. `in_mh`, `in_cg`, `in_ts`) · foreign ISO-2
  (`us`, `jp`, `gb`, `hk`) · `world`.
- measure: index, infl_yoy (official YoY %), current/constant (NAS), usd/inr (amounts), rate, avg, eop,
  high, low, close, ….
- freq is always last (d/w/m/q/a/o) because official annual and quarterly series share a period_start.
- Examples: `cpi.b2024.in.combined.general.index.m` · `cpi.b2012.in_mh.combined.general.index.m` ·
  `nas.b2022_23.in.gdp.constant.q` · `trade.in.exports.oil.usd.m` · `eq.in.nifty50.close.d`.

### core
- `core.observation` — series_id, period_start, period_end, freq, value numeric, estimate_stage
  (advance_1, advance_2, provisional, revised_1..3, final), vintage_at timestamptz, source_run_id, raw_ref.
  PK (series_id, period_start, vintage_at), which also serves lookups by (series_id, period_start).
  **Append-only, enforced by trigger**: UPDATE, DELETE and TRUNCATE raise for every role.
- View `core.latest` — latest vintage per (series_id, period_start).
- Numeric only. Text-valued data (RBI policy stance, MPC vote, event notes on O01) needs a new migration
  — a text column or an events table — in Phase 8/9.

### raw
- Created with their adapters once the payload shape is known: `raw.cpi_detail` (full CPI item × state ×
  sector detail, Phase 2), `raw.mandi_price` (Phase 3). Partition by year when > ~10 M rows.

### derived
- `derived.observation` — series_id, freq (target frequency), period_start, period_end, method
  (mean/sum/end/max/min/link/pop_pct/yoy_pct/pop_bps/yoy_bps/pop_diff; pop = period over period),
  value, is_partial, derived_from, computed_at. PK (series_id, freq, method, period_start). Rebuilt
  idempotently. Covers W/M/Q/FY aggregates, change metrics, linked series.

### ops
- `ops.pipeline_run` (run_id = the log run_id), `ops.source_run` (status, rows_new, rows_revised,
  latest_period, error; index (source_id, started_at DESC)), `ops.quality_issue`, `ops.alert`,
  `ops.schema_migrations` (version, filename, checksum over LF-normalised text, applied_at).

### Periods
- Weekly: week_start = Saturday, week_end = Friday ("Week ending (Fri)" on W sheets).
- PLFS annual: July–June (AY) up to 2023-24, calendar year (CY) from 2025; period_start/period_end follow
  the actual survey period.

### Roles
- `econdb_owner` — owns all objects; runs `econdb migrate` and `econdb seed`.
- `econdb_writer` (NOLOGIN, `db/bootstrap_roles.sql`) — pipeline sessions `SET ROLE econdb_writer`:
  SELECT everywhere, INSERT/UPDATE on meta, INSERT only on raw and core, full DML on derived and ops;
  no DDL, no access to ops.schema_migrations.
- `econdb_reader` (NOLOGIN) — SELECT on all schemas; people and tools become members later.

Write rule: an incoming value is inserted only if (series_id, period_start) is new or its value/estimate
stage differs from `core.latest`. Re-running a job adds nothing.

## 5. Source adapters
Interface (`sources/base.py`):
`discover()` → series definitions · `fetch(since)` → raw payloads (archived) ·
`normalise(payload)` → DataFrame[series_id, period_start, period_end, freq, value, estimate_stage] ·
`validate(df)` → issues. The runner loads rows and records `ops.source_run`.
Shared helpers: HTTP session (UA, timeouts, retries/backoff, rate limit), pagination, gzip archive.

## 6. Scheduling
`econdb run --due` checks each `meta.source.schedule` and runs what is due. Typical windows (IST):
markets/FX/commodities daily 18:30 · mandi daily 20:00 · MoSPI daily 19:00 (releases usually 16:00) ·
RBI weekly Friday 19:30 · monthly downloads daily during their release windows.
Derive and publish run after loads; publish writes only changed cells.

## 7. Monitoring & alerts
- Freshness: compare latest_period with `meta.release_calendar`; late → alert.
- Failures: any failed source run → GitHub Issue via API (label `pipeline-failure`), closed automatically on next success.
- Quality: range, jump (> n σ), duplicates, unit mismatch; cross-checks (e.g. trade RBI vs Commerce).

## 8. Backups
Nightly `pg_dump -Fc` (compressed) + raw-archive sync → off-site (Supabase Storage bucket, Google Drive
via service account, or another provider). Keep 14 daily + 8 weekly + 12 monthly. Monthly restore test.

## 9. Security
SSH keys only, password login off; econdb opens no public ports (80/443/888/12844 serve the
co-hosted Bharat Laws app and aaPanel — see §2); PostgreSQL bound to localhost; pipeline runs as
non-root `econdb` user with systemd `MemoryMax`; separate DB roles (`econdb_owner`, `econdb_writer`,
`econdb_reader`); automatic security updates; fail2ban; secrets in env files with 600 permissions;
Google Sheets shared with named members only. Hardening backlog: Phase 7 in `docs/phases.md`.

## 10. Capacity
Curated `core` + `derived` ≈ low hundreds of MB; raw tables (mandi ≈ 2.4 M rows/yr, CPI detail) and
archive ≈ a few GB over several years — well within the VPS's 65 GB free (shared host: RAM is
7.8 GB with no swap until Phase 7 adds 2–4 GB, so keep the pipeline under `MemoryMax`). Plain PostgreSQL with good
indexes is sufficient; revisit partitioning/TimescaleDB only if queries slow down.
