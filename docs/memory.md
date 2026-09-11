# Project memory — living document (update at the end of every session/phase)

## Current status
- Phase: **0 – Setup: approved 2026-09-11 and pushed to `origin main`.**
  Next: Phase 1 (schema & catalogue), starting with a plan for owner approval.
- Last updated: 2026-09-11 (Claude Code, Phase 0 checkpoint)

## Environment
| Item | Value |
|---|---|
| Local OS / shell | Windows, PowerShell |
| Tools | Python 3.12.9 (project `.venv`) · Git 2.53 · Claude Code 2.1.260. The `py` launcher defaults to **3.14** — create venvs with `py -3.12` |
| Python packages | Pinned in `pyproject.toml` (hatchling, src layout): `psycopg[binary]` 3.3.5, `python-dotenv` 1.2.3; dev extra: `pytest` 9.1.1, `ruff` 0.16.7. Console script `econdb` |
| Repo | `SachinPandit09/India-econ-db` (private) · local path `D:\India-econ-db` |
| Local PostgreSQL | **16.14** (Windows service `postgresql-x64-16`) · `localhost:5432` · `psql` on PATH · DB `econdb` (UTF8, owner `econdb_owner`, CONNECT revoked from PUBLIC) created 2026-09-11 by the owner with `db/bootstrap.sql` + `\password` — **do not re-run the bootstrap** · `econdb_owner` has no CREATEROLE · existing DB `rohingya_as_wb` belongs to another project — never touch it |
| `.env` (git-ignored, complete) | `DATABASE_URL` (no password in it), `PGPASSWORD`, `DATAGOVIN_API_KEY`, `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE`, `GITHUB_REPO`, `GITHUB_TOKEN` — names only here, never values |
| Production VPS | Host IT Smart (LIN VPS – SM 2) · data centre Gujarat, India (AS138246 Netclues) · Ubuntu 22.04.5 LTS · 2 vCPU · 7.8 GB RAM · **no swap** · 97 GB disk (65 GB free) · IP 103.168.18.138 · hostname vps.sachinp.com · paid until 2027-06-04 · plan: PostgreSQL 16 (PGDG) |
| VPS co-tenants (**hands off**, see rules.md) | Shared with the live production app Bharat Laws: `bharatlaws-backend` (Flask/Gunicorn on 127.0.0.1:5000), nginx (80/443/888), MySQL (3306, not reachable externally — confirmed), aaPanel/BT-Panel (`/www`, port 12844, publicly reachable), Acronis backup agents, sendmail |
| VPS firewall | ufw + aaPanel ipset, default deny. Publicly open: 7576 (SSH), 80, 443, 12844, 888, 20/21/39000–40000 (FTP, nothing listening), 22 (unused) |
| VPS access notes | Root access restored and root password changed (Sep 2026). SSH on port 7576 (stays there — 443 belongs to nginx). Port 7576 is blocked on the owner's office/institute Wi-Fi: works there via Cloudflare WARP, or use a mobile hotspot. Tailscale to be set up in Phase 7 |
| VPS backup | Acronis Cloud Backup 10 GB — agent installed, protection plan not yet created (Phase 7 backlog) |
| Supabase | Project `njbbnyvgxvyorwrooagz` (Mumbai, free). No longer the primary DB; optional off-site backup target |
| Claude Code MCP (this folder) | `github`, `supabase` |
| Google Sheets | Spreadsheet "Econdb" owned by sachin.official1218@gmail.com (ID in `.env` as `GOOGLE_SHEET_ID`) · GCP project `econdb-508308` · service account `econdb-sheets@econdb-508308.iam.gserviceaccount.com` with Editor on the sheet · key file outside the repo (path in `.env`) · read-only gspread test connected OK (2026-09-11) · Apps Script / Playwright automation deferred to Phase 5, optional |
| GitHub token | Fine-grained, repo-scoped, expires 2026-12-09 — renew before then |

## Decisions log
| Date | Decision | Why |
|---|---|---|
| 2026-09-11 | PostgreSQL: develop locally, then run production on the owner's VPS | 100 GB disk removes Supabase's 500 MB limit; full control |
| 2026-09-11 | PostgreSQL **16** locally and on the VPS (VPS needs the official PGDG repo; Ubuntu 22.04 ships 14) | Migration by dump/restore without surprises |
| 2026-09-11 | Scheduler runs on the VPS (systemd timers); GitHub holds code, CI and failure issues | Indian IP for government sites; no Actions minutes or 60-day inactivity limits |
| 2026-09-11 | Append-only observations with vintages; base years never mixed | Revisions and 2026 rebasing (GDP, CPI, IIP, WPI) |
| 2026-09-11 | Tracker: 6 frequency categories (Annual, Quarterly, Monthly, Weekly, Daily, Occasional), 87 sheets, oldest rows at top, history collapsed to latest rows | Owner's layout decisions — see `docs/design.md` |
| 2026-09-11 | Financial year (Apr–Mar) is the default period basis | Indian official statistics convention |
| 2026-09-11 | Internal team use only; nothing published | Allows Yahoo data internally; licensed data still excluded |
| 2026-09-11 | `DATABASE_URL` carries no password; the password lives in `PGPASSWORD` (read natively by libpq/psycopg and `pg_dump`) | No URL-encoding of special characters; errors and logs can never echo the secret |
| 2026-09-11 | `db/bootstrap.sql` = one-time superuser setup (role + DB), not a migration; reused on the VPS. Phase 1 reader/writer roles will be proposed as separate superuser SQL | `econdb_owner` stays unprivileged (no CREATEROLE) |
| 2026-09-11 | CLI on stdlib `argparse`; exact pins in `pyproject.toml`, no separate `requirements.txt` (a `pip freeze` lock can be added for the Phase 7 deploy) | Fewest dependencies and files |
| 2026-09-11 | The VPS is shared with Bharat Laws: hands-off rules, non-root `econdb` user with `MemoryMax`, changes only in maintenance windows | Must never disturb a live production app |
| 2026-09-11 | "SSH on port 443" dropped (nginx owns 443) | Port conflict with Bharat Laws |
| 2026-09-11 | CPI detail: full detail (every item × state × sector) in a `raw` table; curated `core` series = All-India at all levels (division → item) × rural/urban/combined, plus states at headline and division level | Full history kept, curated layer stays tracker-sized |
| 2026-09-11 | VPS maintenance window decided in Phase 7 (proposed Sunday 02:00–04:00 IST) | Needs Bharat Laws sign-off |
| 2026-09-11 | Tailscale: yes, set up in Phase 7 for private VPS/DB access | No public DB or extra public ports |
| 2026-09-11 | Google Sheet stays owned by sachin.official1218@gmail.com; a FinSkeptics account may take over later | Owner's choice |
| 2026-09-11 | `*.md` excluded from ruff | Docs must never be reformatted |

## Verified source findings (from explore/ runs, 11-Sep-2026)
**MoSPI e-Sankhyiki (`mospi-esankhyiki` 0.1.4, no key)**
- 30 datasets. `get_data` returns 10 rows per page by default → always pass `limit` + `page` and loop.
- The package prints full raw responses and disables SSL verification → silence stdout around calls,
  suppress `InsecureRequestWarning`.
- Required metadata params: PLFS `year_type_code` (1 = agri/FY, 2 = calendar); RBI `sub_indicator_code`;
  ENERGY `use_of_energy_balance_code` (1 = supply, 2 = consumption).
- NAS indicator-list endpoint returned HTTP 500; codes 1–22 work directly (code 1 = GVA).
  Quarterly exists for codes 1, 2, 5, 9–15, 21, 22; annual only for 3, 4, 6, 7, 8, 16–20.
  2022-23 "Back" series not yet published (expected by Dec 2026).
- CPI base 2024: index AND inflation returned; one month at full detail > 5,000 rows.

| Series | Coverage found |
|---|---|
| GDP/GVA | 2011-12 base FY2011-12→FY2025-26 (A & Q); 2022-23 base FY2022-23→FY2025-26 (A), Q to FY2026-27 Q1 |
| CPI | 2010 base 2011→2014; 2012 base 2011→2025; 2024 base live |
| WPI | 1993-94: 1994→2010 · 2004-05: 2005→2017 · 2011-12: 2012→2026 · 2022-23: 2023→2026 |
| IIP | 1993-94: 1994→2011 · 2004-05: 2005→2017 · 2011-12: 2012→2026 · 2022-23: 2023→2026 |
| CPI-AL/RL | 1999-2000→2026 (bases 1986-87, 2019) |
| PLFS | annual 2017-18→2025 · quarterly 2018→2026 · monthly 2025→2026 |
| RBI via MoSPI | forex reserves annual 1950-51→; BoP key components 1950-51→; trade annual 1970-71→, monthly 1990-91→; exchange rates monthly 1966→; ext. debt 1991→ |
| ASI | 2004-05→2023-24 · Energy balance 2012-13→2023-24 · MNRE 2020→2026 |

**data.gov.in** — key in `.env` as `DATAGOVIN_API_KEY`. Slow: first call timed out; works with a
browser User-Agent, small `limit`, retries. Mandi resource `9ef84268-d588-465a-a308-a864a43d0070`
returns only the current day (6,612 rows on 11-Sep-2026) → capture daily to build history.

**Yahoo (yfinance 1.7.0)** — 42/43 tickers OK. `^CNXSC` dead; `CNYINR=X` has 1 row (drop).
Sector indices have gaps. Nifty from 2007-09-17, Sensex from 1997-07-01. Keep ≥1.5 s between calls.

**Tooling quirks**
- ruff 0.16 `ruff format` also formats Python code blocks inside Markdown files, so `*.md` and
  `explore/` are both in ruff's `extend-exclude`.

## Open questions
- None open. (Maintenance window date is scheduled for decision in Phase 7.)

## Session notes (newest first)
- 2026-09-11 (Phase 0): Repo skeleton, `.venv`, pinned deps, `econdb` CLI with `db-check`, ruff + pytest set up.
  Owner ran `db/bootstrap.sql`, set the role password, completed `.env`, set up the Google Sheets service account.
  `econdb db-check` OK (econdb_owner → econdb, PostgreSQL 16.14); 2 tests pass; ruff clean. VPS facts, VPS rules
  and Phase 7 changes recorded in rules/architecture/phases. Committed locally, not pushed.
- 2026-09-11: Local PostgreSQL 16.14 confirmed and admin password changed. VPS reachable only via hotspot; root password reset requested from Host IT Smart.
- 2026-09-11: Project docs created; exploration complete; ready for Phase 0.
