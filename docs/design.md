# Design — Google Sheets tracker

Canonical layout: `docs/reference/India_Econ_Tracker_Layout.xlsx` (87 indicator sheets + CONTENTS + RULES).
The publisher must reproduce it exactly; this document states the rules behind it.

## 1. Workbook structure
- Sheet 1 `CONTENTS`: table of contents with colour-coded frequency legend (live counts), then one row
  per sheet: #, Frequency, Sheet (hyperlink), Indicator, Base-year/column blocks, Coverage, Source,
  Access, Type (Official/Derived), Derived from, Status. Header frozen, filter on.
- Sheet 2 `RULES`: categories, base-year rules, aggregation rules, change formulas, how to see history.
- Then indicator sheets grouped in this order: Annual, Quarterly, Monthly, Weekly, Daily, Occasional.

## 2. Categories, colours and sheet names
| Category | Prefix | Dark | Mid (tab) | Light |
|---|---|---|---|---|
| Annual | A | #1F4E79 | #2E75B6 | #DDEBF7 |
| Quarterly | Q | #375623 | #548235 | #E2EFDA |
| Monthly | M | #843C0C | #C55A11 | #FBE5D6 |
| Weekly | W | #3F1F5C | #7030A0 | #E4DFEC |
| Daily | D | #7B1010 | #C00000 | #F8D7D7 |
| Occasional | O | #404040 | #7F7F7F | #EDEDED |
Sheet name = prefix + 2-digit number + short name, e.g. `M06_WPI`, `D01_Markets_India_Daily`.

## 3. Every indicator sheet
- **Row 1:** `◄ Contents` link (A1) + title bar: title · source · unit · frequency · coverage.
- **Row 2:** column-block titles (merged across the block), alternating mid/dark category colour.
- **Row 3:** column names on light category colour, wrapped, centred.
- **Frozen:** rows 1–3 and the period column(s).
- **Period columns:** Daily `Date` · Weekly `Week ending (Fri)` · Monthly `Month` + `Fiscal year` ·
  Quarterly `Quarter (FY)` (e.g. `2026-27 Q2`) + `Months` · Annual `Fiscal year` (`2025-26`);
  calendar-year sheets labelled `Calendar year`.
- **Row order:** oldest at the top, newest at the bottom.
- **Collapsed history:** rows older than the latest N are grouped and collapsed (+ button above the group):
  Daily 50 · Weekly 50 · Monthly 36 · Quarterly 24 · Annual 25. Occasional sheets are not grouped.
- **Fonts/format:** Arial 10; numbers `#,##0.00` (₹ crore levels `#,##0`); % `0.0%`; bps `0`.
- **Periods in progress** (derived only): period cell in grey italics with a note "values as of <date>".

## 4. Base years
One sheet per indicator; each base year is its own column block titled with base and coverage,
e.g. `Base 2011-12=100 (2012→2026)`. Empty cells mean that base did not exist for that period.
An optional `Linked series (…=100)` block uses only official linking factors.

## 5. Derived sheets and change blocks
- Derived sheets live in their target category (e.g. `Q08_CPI_Quarterly`, `A18_CPI_Annual`) and show
  `Type = Derived` and `Derived from` on CONTENTS.
- Computed change blocks have a yellow header (#FFD966) and pale-yellow column names (#FFF2CC):
  daily %, week-on-week %, MoM %, QoQ %, YoY % (12 months / 4 quarters / 52 weeks), FY change %.
  Rates and yields change in basis points. Formulas return blank when either input is missing.

## 6. Publishing behaviour
- Data cells are written as values; change blocks remain formulas.
- Incremental: only new/changed cells are written; new periods append at the bottom and the
  collapsed group is extended so the latest N rows stay visible.
- New series inside an existing block → new column at the end of that block (never reorder existing columns).
- Optional Apps Script (editors only): on opening a tab, jump to the newest row.

## 7. Access
Spreadsheet `Econdb`, owned by sachin.official1218@gmail.com (a FinSkeptics account may take over
later; ID in `.env` as `GOOGLE_SHEET_ID`);
shared only with named team members; the pipeline writes through the service account
`econdb-sheets@econdb-508308.iam.gserviceaccount.com`, which has Editor access to that one file.
