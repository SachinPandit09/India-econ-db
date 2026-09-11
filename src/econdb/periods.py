"""Period labels -> (period_start, period_end). Financial year = April-March (docs/rules.md)."""

import calendar
from datetime import date

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
QUARTER_MONTHS = {"jan-mar": 1, "apr-jun": 4, "jul-sep": 7, "oct-dec": 10}


def month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def month(year, month_name) -> tuple[date, date]:
    y, m = int(year), MONTHS[str(month_name).strip().lower()]
    return date(y, m, 1), month_end(y, m)


def fy_first_year(label) -> int:
    """'2023-24', '1999-2000', '2024-2025' -> 2023 / 1999 / 2024."""
    first, _, second = str(label).strip().partition("-")
    y = int(first)
    if not second or int(second) % 100 != (y + 1) % 100:
        raise ValueError(f"not a financial-year label: {label!r}")
    return y


def fy(label) -> tuple[date, date]:
    y = fy_first_year(label)
    return date(y, 4, 1), date(y + 1, 3, 31)


def fy_month(label, month_name) -> tuple[date, date]:
    """A month inside a financial-year label: April-December fall in the first year."""
    y, m = fy_first_year(label), MONTHS[str(month_name).strip().lower()]
    return month(y if m >= 4 else y + 1, calendar.month_name[m])


def fy_quarter(label, quarter) -> tuple[date, date]:
    """'2026-27', 'Q1' -> April-June 2026 (Q1 Apr-Jun ... Q4 Jan-Mar)."""
    q = int(str(quarter).strip().upper().lstrip("Q"))
    start_month = (4 + 3 * (q - 1) - 1) % 12 + 1
    y = fy_first_year(label) + (1 if q == 4 else 0)
    return date(y, start_month, 1), month_end(y, start_month + 2)


def quarter_of_month(year, month_name) -> tuple[date, date]:
    """The calendar quarter containing a month (quarter-end stocks, e.g. RBI external debt)."""
    y, m = int(year), MONTHS[str(month_name).strip().lower()]
    start = 3 * ((m - 1) // 3) + 1
    return date(y, start, 1), month_end(y, start + 2)


def named_quarter(year, name) -> tuple[date, date]:
    """PLFS quarterly bulletins: year '2025' + 'Jul-Sep' -> July-September 2025."""
    y, m = int(year), QUARTER_MONTHS[str(name).strip().lower()]
    return date(y, m, 1), month_end(y, m + 2)


def ay_quarter(label, name) -> tuple[date, date]:
    """A quarter inside an agricultural year (Jul-Jun): '2017-18' + 'Jan-Mar' -> Jan-Mar 2018."""
    y, m = fy_first_year(label), QUARTER_MONTHS[str(name).strip().lower()]
    y = y if m >= 7 else y + 1
    return date(y, m, 1), month_end(y, m + 2)


def ay(label) -> tuple[date, date]:
    """Agricultural year July-June (PLFS annual to 2023-24)."""
    y = fy_first_year(label)
    return date(y, 7, 1), date(y + 1, 6, 30)


def cy(label) -> tuple[date, date]:
    y = int(str(label).strip())
    return date(y, 1, 1), date(y, 12, 31)


def end_march(year) -> tuple[date, date]:
    """Stock at end-March of a year: '1991' -> financial year 1990-91."""
    y = int(str(year).strip())
    return date(y - 1, 4, 1), date(y, 3, 31)


# Survey rounds with fieldwork dates (freq 'O' series use explicit periods)
SURVEY_ROUNDS = {
    ("HCES", "2022-23"): (date(2022, 8, 1), date(2023, 7, 31)),
    ("HCES", "2023-24"): (date(2023, 8, 1), date(2024, 7, 31)),
    ("NFHS", "nfhs-3"): (date(2005, 11, 1), date(2006, 8, 31)),
    ("NFHS", "nfhs-4"): (date(2015, 1, 1), date(2016, 12, 31)),
    ("NFHS", "nfhs-5"): (date(2019, 6, 1), date(2021, 4, 30)),
}


def survey(dataset: str, label) -> tuple[date, date]:
    try:
        return SURVEY_ROUNDS[(dataset, str(label).strip().lower())]
    except KeyError:
        raise ValueError(
            f"unknown {dataset} survey round {label!r} - add it to SURVEY_ROUNDS"
        ) from None
