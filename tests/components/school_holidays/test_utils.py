"""Test utils.py for School Holidays integration."""

from datetime import date

import pytest

from homeassistant.components.school_holidays import utils

from .conftest import (
    TEST_SPRING_BREAK_DESCRIPTION,
    TEST_SPRING_BREAK_END,
    TEST_SPRING_BREAK_NAME,
    TEST_SPRING_BREAK_START,
)


def test_clean_string() -> None:
    """Test that HTML character entities are removed and leading/trailing whitespace is stripped."""
    assert (
        utils.clean_string(
            f"\n        \n            &sup1; {TEST_SPRING_BREAK_DESCRIPTION}\n         \n    "
        )
        == TEST_SPRING_BREAK_DESCRIPTION
    )
    assert utils.clean_string(None) is None


def test_create_calendar_event() -> None:
    """Test that a calendar event is created and appended to the events list."""
    events = []

    utils.create_calendar_event(
        events,
        summary=TEST_SPRING_BREAK_NAME,
        start=TEST_SPRING_BREAK_START,
        end=TEST_SPRING_BREAK_END,
        description=TEST_SPRING_BREAK_DESCRIPTION,
    )

    assert len(events) == 1
    assert events[0]["summary"] == TEST_SPRING_BREAK_NAME
    assert events[0]["start"] == TEST_SPRING_BREAK_START
    assert events[0]["end"] == TEST_SPRING_BREAK_END
    assert events[0]["description"] == TEST_SPRING_BREAK_DESCRIPTION


def test_ensure_date() -> None:
    """Test that a string is converted to a date object."""
    assert utils.ensure_date("2026-01-01") == date(2026, 1, 1)
    assert utils.ensure_date("2026-01-01T22:59:00Z") == date(2026, 1, 1)
    assert utils.ensure_date(date(2026, 1, 1)) == date(2026, 1, 1)

    # Test with invalid date string raises ValueError
    with pytest.raises(ValueError):
        utils.ensure_date("invalid-date")

    # Test with None raises TypeError
    with pytest.raises(TypeError):
        utils.ensure_date(None)


def test_generate_unique_id() -> None:
    """Test that unique ID is normalized to lowercase with underscores."""
    assert (
        utils.generate_unique_id("The Netherlands", "Midden")
        == "the_netherlands_midden"
    )
