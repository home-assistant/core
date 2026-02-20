"""Test utils.py for School Holiday integration."""

from datetime import date

import pytest

from homeassistant.components.school_holiday import utils

SUMMARY = "Spring Break"
START = "2026-02-14"
END = "2026-02-22"
DESCRIPTION = "Spring Break for the region Midden."


def test_clean_string() -> None:
    """Test that HTML character entities are removed and leading/trailing whitespace is stripped."""
    assert (
        utils.clean_string(
            f"\n        \n            &sup1; {DESCRIPTION}\n         \n    "
        )
        == DESCRIPTION
    )
    assert utils.clean_string(None) is None


def test_create_calendar_event() -> None:
    """Test that a calendar event is created and appended to the events list."""
    events = []

    utils.create_calendar_event(
        events,
        summary=SUMMARY,
        start=START,
        end=END,
        description=DESCRIPTION,
    )

    assert len(events) == 1
    assert events[0]["summary"] == SUMMARY
    assert events[0]["start"] == START
    assert events[0]["end"] == END
    assert events[0]["description"] == DESCRIPTION


def test_ensure_date() -> None:
    """Test that a string is converted to a date object."""
    test_date = date(2026, 1, 1)

    assert utils.ensure_date("2026-01-01") == test_date
    assert utils.ensure_date("2026-01-01T22:59:00Z") == test_date
    assert utils.ensure_date(test_date) == test_date

    # Testing with an invalid date string should raise a ValueError.
    with pytest.raises(ValueError):
        utils.ensure_date("invalid-date")

    # Testing with None should raise a TypeError.
    with pytest.raises(TypeError):
        utils.ensure_date(None)
