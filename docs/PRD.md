# PRD — India Economic Database & Tracker (FinSkeptics internal)

## 1. Problem
India's economic data is scattered across MoSPI, RBI, ministries, exchanges and dozens of PDFs,
released on different days, revised often, and rebased every decade (all four headline series —
GDP, CPI, IIP, WPI — were rebased in 2026). Tracking it by hand is slow and error-prone.

## 2. Goal
A self-updating, single source of truth for Indian macro and market data that:
- collects every indicator in scope automatically with no monthly manual work,
- keeps full history across all base years and every revision (vintage),
- derives weekly / monthly / quarterly / FY views and change metrics consistently,
- publishes a clean, colour-coded Google Sheets tracker the team can use immediately.

## 3. Users
FinSkeptics team (internal only). Analysts and writers who need fast, trustworthy numbers,
long history and the latest release without hunting through websites.

## 4. Scope
**In scope**
- ~200 indicator families across 17 themes (see `docs/reference/India_Econ_Indicator_Catalogue.xlsx`).
- Sources by tier: T1 MoSPI API (incl. 39 RBI datasets); T1b data.gov.in, Yahoo, World Bank/IMF/BIS;
  T2 structured downloads (RBI DBIE, OEA, CGA, AMFI, FBIL, PPAC, Grid-India, CEA…);
  T3 scrapers/PDF (GST, EPFO, NSDL, Vahan, CWC, IMD, DGCA…); T4 manual annual (Union Budget, MSP).
- PostgreSQL database (local → VPS), raw archive, derived layer, Google Sheets tracker (87 sheets).
- Monitoring, alerts, backups.

**Out of scope (for now)**
- Public website or public API; any redistribution of data.
- Paid/licensed datasets (PMI detail, CMIE, SIAM detail, private real estate).
- Forecasting models (a later "analytics" phase may add nowcasts).

## 5. Functional requirements
| ID | Requirement |
|---|---|
| FR1 | Catalogue-driven: every series defined in `meta.series`; adding a series needs no new code where its source adapter exists |
| FR2 | Adapters per source with fetch → normalise → validate → load; independent failure |
| FR3 | Append-only storage of every value with `vintage_at`, estimate stage and source reference |
| FR4 | All base years stored as separate series; linked series via official linking factors |
| FR5 | Raw archive of every downloaded response/file |
| FR6 | Derived layer: W/M/Q/FY aggregates by `agg_rule`; daily %, WoW, MoM, QoQ, YoY, FY change; bps for rates |
| FR7 | Scheduler with per-source schedules (daily, weekly, monthly release windows) |
| FR8 | Freshness monitoring against an expected release calendar; alert when late or failed |
| FR9 | Data-quality checks: ranges, jumps, duplicates, unit mismatch, cross-source reconciliation |
| FR10 | Google Sheets publisher that reproduces `docs/design.md` exactly, updates incrementally |
| FR11 | Backups: nightly database dump + raw archive copied off the VPS |
| FR12 | CLI: `econdb migrate`, `econdb run --source X`, `econdb run --due`, `econdb backfill`, `econdb publish` |

## 6. Non-functional requirements
- **Freshness:** data in the tracker within 24 h of official release (markets: same evening).
- **Reliability:** one broken source never blocks others; failed runs raise a GitHub issue.
- **Cost:** ≈ ₹0 beyond the VPS. Free tiers only for anything external.
- **Security:** DB not internet-facing; secrets never in git; Sheets shared only with named team members.
- **Portability:** identical code and PostgreSQL major version locally and on the VPS.
- **Traceability:** every number traceable to source URL/params, fetch time and raw file.

## 7. Success metrics
- ≥ 95% of scheduled source runs succeed each month; failures alerted within one run.
- 100% of P1 indicators live with full available history within the first build cycle.
- Zero manual edits needed to keep the tracker current for 30 consecutive days.

## 8. Constraints & risks
- Government sites are slow, change without notice, and may block foreign IPs → retries, raw archive, Indian VPS.
- MoSPI endpoints can return HTTP 500 → fallbacks (e.g. NAS codes 1–22 probed directly).
- Yahoo is unofficial and gappy → official sources preferred where they exist.
- Frequent rebasing and revisions → vintages + base-year-aware design.
