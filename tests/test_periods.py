from datetime import date

import pytest

from econdb import periods


def test_financial_year_labels():
    assert periods.fy("2023-24") == (date(2023, 4, 1), date(2024, 3, 31))
    assert periods.fy("1999-2000") == (date(1999, 4, 1), date(2000, 3, 31))
    with pytest.raises(ValueError):
        periods.fy("2023-25")


def test_months_and_fy_months():
    assert periods.month(2024, "February") == (date(2024, 2, 1), date(2024, 2, 29))
    assert periods.fy_month("2024-2025", "January") == (
        date(2025, 1, 1),
        date(2025, 1, 31),
    )  # CPI-AL/RL
    assert periods.fy_month("2026-27", "June") == (
        date(2026, 6, 1),
        date(2026, 6, 30),
    )  # ISP, RBI 12


def test_quarters():
    assert periods.fy_quarter("2026-27", "Q1") == (date(2026, 4, 1), date(2026, 6, 30))
    assert periods.fy_quarter("2025-26", "Q4") == (date(2026, 1, 1), date(2026, 3, 31))
    assert periods.named_quarter("2025", "Jul-Sep") == (date(2025, 7, 1), date(2025, 9, 30))
    assert periods.ay_quarter("2017-18", "Jan-Mar") == (date(2018, 1, 1), date(2018, 3, 31))
    assert periods.quarter_of_month("2024", "December") == (date(2024, 10, 1), date(2024, 12, 31))


def test_year_bases():
    assert periods.ay("2017-18") == (date(2017, 7, 1), date(2018, 6, 30))
    assert periods.cy("2025") == (date(2025, 1, 1), date(2025, 12, 31))
    assert periods.end_march("1991") == (date(1990, 4, 1), date(1991, 3, 31))
    assert periods.survey("HCES", "2023-24") == (date(2023, 8, 1), date(2024, 7, 31))
    with pytest.raises(ValueError):
        periods.survey("NFHS", "nfhs-9")
