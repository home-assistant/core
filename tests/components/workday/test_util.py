"""Unit tests for the workday validate_dates helper."""

from __future__ import annotations

import pytest

from homeassistant.components.workday.util import validate_dates


@pytest.mark.parametrize(
    ("holiday_list", "expected"),
    [
        # Single valid date → passed through as-is
        (["2024-01-01"], ["2024-01-01"]),
        # Multiple single dates → all preserved in order
        (["2024-01-01", "2024-12-25"], ["2024-01-01", "2024-12-25"]),
        # A two-day range (inclusive) → expanded to individual dates
        (
            ["2024-03-01,2024-03-03"],
            ["2024-03-01", "2024-03-02", "2024-03-03"],
        ),
        # Same-day range → single date
        (["2024-06-15,2024-06-15"], ["2024-06-15"]),
        # Mix of single dates and a range
        (
            ["2024-01-01", "2024-03-01,2024-03-02"],
            ["2024-01-01", "2024-03-01", "2024-03-02"],
        ),
        # Invalid single date string → skipped (returned list is empty)
        (["not-a-date"], ["not-a-date"]),
        # Invalid date range (second date is malformed) → skipped with an error log
        (["2024-01-01,not-a-date"], []),
        # Empty list → empty result
        ([], []),
    ],
)
def test_validate_dates(holiday_list: list[str], expected: list[str]) -> None:
    """Test that validate_dates correctly parses dates and date ranges."""
    assert validate_dates(holiday_list) == expected


def test_validate_dates_leading_comma_is_skipped() -> None:
    """Test that a string starting with a comma is treated as a date range.

    The first segment is an empty string which parse_date cannot parse,
    so the entry is logged as an error and skipped.
    """
    # ",2024-01-01" → find(",") == 0 → treated as range → dates[0] == "" → skipped
    result = validate_dates([",2024-01-01"])
    assert result == []
