# Build phases

Every phase ends with a **checkpoint**: Claude Code stops, summarises what was done with evidence
(row counts, sample values vs. official releases, test output), updates `docs/memory.md`, and waits for approval.

## Phase 0 — Project setup (local)
- Repo structure per `docs/architecture.md`; `pyproject.toml`/`requirements.txt`; `.venv`; ruff; pytest.
- `.env.example` (DATABASE_URL, DATAGOVIN_API_KEY, GOOGLE_SERVICE_ACCOUNT_FILE, GITHUB_REPO, GITHUB_TOKEN …).
- `.gitignore`: `.env`, `.venv/`, `data/`, `logs/`, `__pycache__/`, `explore/output/`.
- Local PostgreSQL 16.14 is confirmed. Create database `econdb` and role `econdb_owner` (ask before creating);
  the owner types the role's password into `.env` — never into the chat. Do not touch other databases.
- Minimal CLI skeleton (`python -m econdb --help`).
- **Checkpoint:** `econdb --help` works; DB connection test passes; repo committed.

## Phase 1 — Schema & catalogue
- Migrations: schemas `meta, raw, core, derived, ops`; tables and views per architecture §4; roles/grants.
- Migration runner (`econdb migrate`) with `ops.schema_migrations`.
- Seed `meta.source`, `meta.series` and `meta.sheet_column` from the two reference workbooks
  (start with the sheets whose sources are verified: MoSPI, RBI-via-MoSPI, Yahoo).
- Seed `meta.linking_factor` rows (values filled later from official notices).
- **Checkpoint:** schema diagram/summary, count of series per source, sample series_ids approved.

## Phase 2 — MoSPI adapter + backfill
- Adapter covering CPI (2024/2012/2010), WPI (4 bases), IIP (4 bases), NAS (codes 1–22, both bases),
  PLFS (A/Q/M), CPI-AL/RL, ASI, ISP, ENERGY, MNRE, RBI datasets (39 codes), HCES.
- Pagination, required params, NAS fallback, stdout silencing, retries, raw archive.
- Full-history backfill; idempotent re-run adds zero rows.
- **Checkpoint:** rows per dataset; 5 spot checks against MoSPI/RBI press releases; tests green.

## Phase 3 — Daily sources: Yahoo + data.gov.in (mandi)
- Yahoo adapter for the tickers in the layout (close + volume; drop `^CNXSC`, `CNYINR=X`).
- data.gov.in adapter (browser UA, small pages, retries) → `raw.mandi_price`, daily capture.
- **Checkpoint:** daily history loaded; mandi capture runs twice without duplicates.

## Phase 4 — Derived layer
- Aggregations by `agg_rule` (D→W/M/Q/FY; M→Q/FY), completeness + `is_partial`.
- Change metrics (daily %, WoW, MoM, QoQ, YoY, FY, bps) and linked series (once factors exist).
- **Checkpoint:** derived values match hand calculations for 3 series; partial periods flagged.

## Phase 5 — Google Sheets publisher
- Service account and spreadsheet `Econdb` already set up by the owner (see `docs/memory.md`);
  build the tracker exactly per `docs/design.md` and the layout workbook.
- Optional: Apps Script (jump to newest row) / Playwright automation.
- CONTENTS, RULES, colours, frozen panes, blocks, formulas, collapsed history, incremental updates.
- **Checkpoint:** owner reviews the live spreadsheet; second publish writes only changed cells.

## Phase 6 — Scheduler, monitoring, backups (still local)
- `econdb run --due` with per-source schedules; freshness vs release calendar; quality checks;
  GitHub Issue alerts; nightly backup script (tested restore).
- **Checkpoint:** a deliberately broken source raises an issue; backup restores into a scratch DB.

## Phase 7 — Move to the VPS
The VPS is shared with the live Bharat Laws app — follow the VPS rules in `docs/rules.md`.
- Hardening — ask before each change; reboots, OS upgrades and firewall changes only with approval
  in a planned maintenance window. Security backlog: SSH keys only with password login off;
  fail2ban; restrict ports 12844 (aaPanel) and 888; close the FTP ports (20/21/39000–40000) and 22;
  auto-updates; create the Acronis protection plan; off-site `pg_dump` backups.
- SSH stays on port 7576 (443 belongs to nginx — the "SSH on 443" idea is dropped).
  Set up Tailscale for private access (decided 2026-09-11).
- Agree the maintenance window with Bharat Laws (proposed Sunday 02:00–04:00 IST).
- Add 2–4 GB swap (the host has none).
- PostgreSQL 16 from the PGDG repository on `localhost:5432` only; roles; `/etc/econdb/econdb.env`;
  code in `/opt/econdb`; dedicated non-root `econdb` Linux user; systemd units with `MemoryMax`.
- `pg_dump`/`pg_restore` local → VPS; systemd service + timers.
- Plan the Ubuntu 22.04 → 24.04 upgrade (standard support ends April 2027) inside a Bharat Laws
  maintenance window.
- **Checkpoint:** 7 consecutive days of successful scheduled runs on the VPS; tracker current.

## Phase 8 — Tier 2 downloads
RBI DBIE (money, credit, rates, reserves weekly, REER), OEA (core 8, WPI food, PPI), CGA, AMFI, FBIL,
PPAC, Grid-India, CEA, NSDL FPI, RBI surveys, house prices. One adapter per source, one checkpoint each.

## Phase 9 — Tier 3 scrapers & PDFs
GST, EPFO payroll, e-way bills, UPI/FASTag (NPCI), Vahan (Playwright), CWC reservoirs, IMD rainfall,
sowing, DGCA, railways, crop estimates, MSP, FSR. Each with raw archive + parser tests.

## Phase 10 — Hardening & extras
Documentation, data dictionary auto-generated from `meta.series`, performance tuning,
optional internal dashboard, nowcast/composite indicators.
