"""Test utils.py for School Holiday integration."""

from datetime import date

import pytest

from homeassistant.components.school_holiday import utils

SUMMARY = "Autumn Holiday"
START = date(2026, 10, 17)
END = date(2026, 10, 25)
DESCRIPTION = "A week's holiday for school and college students in the autumn."


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
    assert utils.ensure_date("2026-01-01T23:59:00Z") == test_date
    assert utils.ensure_date(test_date) == test_date

    # Testing with an invalid date string should raise a ValueError.
    with pytest.raises(ValueError):
        utils.ensure_date("invalid-date")

    # Testing with None should raise a TypeError.
    with pytest.raises(TypeError):
        utils.ensure_date(None)


def test_get_device_name() -> None:
    """Test that device name is generated correctly from country and region codes."""
    assert utils.get_device_name("nl", "midden") == "The Netherlands - Central"
    assert utils.get_device_name("nl", "noord") == "The Netherlands - North"
    assert utils.get_device_name("nl", "zuid") == "The Netherlands - South"
