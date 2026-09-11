# India Economic Database — FinSkeptics (internal use only)

Automated database of Indian economic indicators: collect from official APIs, downloads and
scrapers → store every value and revision in PostgreSQL → derive daily/weekly/monthly/quarterly/FY
views → publish a colour-coded Google Sheets tracker for the team.

## Always-loaded context
@docs/rules.md
@docs/memory.md

## Read when the task needs it (not auto-loaded)
- `docs/PRD.md` — what we are building, for whom, scope, requirements
- `docs/architecture.md` — components, database schema, data flow, environments, deployment
- `docs/phases.md` — build phases, deliverables and acceptance checkpoints
- `docs/design.md` — Google Sheets tracker layout (categories, colours, blocks, frozen headers)
- `docs/reference/India_Econ_Tracker_Layout.xlsx` — canonical sheet-by-sheet layout (87 sheets)
- `docs/reference/India_Econ_Indicator_Catalogue.xlsx` — indicator universe, sources, verification status
- `explore/` — one-off exploration scripts and their outputs (reference only, not pipeline code)

## Commands (fill in as they are created)
- Create env (Windows, once): `py -3.12 -m venv .venv` then `.\.venv\Scripts\python -m pip install -e ".[dev]"`
  (`py` alone defaults to 3.14 on this machine)
- Activate env (Windows): `.\.venv\Scripts\Activate.ps1`
- DB connection test: `econdb db-check` (or `python -m econdb db-check`)
- Tests: `pytest -q` · Lint/format: `ruff check . ; ruff format .`
- Migrations: `python -m econdb migrate` (`--status` lists applied/pending). One-time superuser setup,
  run by the owner only: `db/bootstrap.sql`, `db/bootstrap_roles.sql`
- Load catalogue + tracker layout into meta: `python -m econdb seed` (idempotent)
- Run one source: `python -m econdb run --source <name>` · Run everything due: `python -m econdb run --due`

## Session workflow
1. Read "Current status" in `docs/memory.md`.
2. Work only on the current phase in `docs/phases.md`; stop at its checkpoint.
3. Before ending a session or closing a phase, update `docs/memory.md`.
