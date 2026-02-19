"""Test calendar platform for School Holidays integration."""

from datetime import date
from unittest.mock import MagicMock

from homeassistant.components.school_holidays.calendar import (
    SchoolHolidaysCalendarEntity,
)
from homeassistant.components.school_holidays.utils import generate_unique_id

from .conftest import (
    TEST_CALENDAR_NAME,
    TEST_COUNTRY,
    TEST_REGION,
    TEST_SPRING_BREAK_DESCRIPTION,
    TEST_SPRING_BREAK_END,
    TEST_SPRING_BREAK_NAME,
    TEST_SPRING_BREAK_START,
    TEST_SUMMER_HOLIDAY_DESCRIPTION,
    TEST_SUMMER_HOLIDAY_END,
    TEST_SUMMER_HOLIDAY_NAME,
    TEST_SUMMER_HOLIDAY_START,
)


def test_calendar_entity_attributes() -> None:
    """Test calendar entity attributes initialization."""
    entity = SchoolHolidaysCalendarEntity(
        None, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    assert entity._attr_name == TEST_CALENDAR_NAME
    assert entity._country == TEST_COUNTRY
    assert entity._region == TEST_REGION


def test_calendar_entity_unique_id() -> None:
    """Test that calendar entity has a unique ID."""
    entity = SchoolHolidaysCalendarEntity(
        None, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    assert entity.unique_id is not None
    assert entity.unique_id == generate_unique_id(TEST_COUNTRY, TEST_REGION)


def test_calendar_entity_has_entity_name() -> None:
    """Test that calendar entity has entity name enabled."""
    entity = SchoolHolidaysCalendarEntity(
        None, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    assert entity.has_entity_name is True


def test_calendar_events_empty() -> None:
    """Test calendar with no events."""
    coordinator = MagicMock()
    coordinator.data = []

    entity = SchoolHolidaysCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    events = entity.events
    assert events == []


def test_calendar_events_with_data() -> None:
    """Test calendar with event data."""
    coordinator = MagicMock()
    coordinator.data = [
        {
            "summary": TEST_SPRING_BREAK_NAME,
            "start": date.fromisoformat(TEST_SPRING_BREAK_START),
            "end": date.fromisoformat(TEST_SPRING_BREAK_END),
            "description": TEST_SPRING_BREAK_DESCRIPTION,
        },
        {
            "summary": TEST_SUMMER_HOLIDAY_NAME,
            "start": date.fromisoformat(TEST_SUMMER_HOLIDAY_START),
            "end": date.fromisoformat(TEST_SUMMER_HOLIDAY_END),
            "description": TEST_SUMMER_HOLIDAY_DESCRIPTION,
        },
    ]

    entity = SchoolHolidaysCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    events = entity.events
    assert len(events) == 2

    assert events[0]["summary"] == TEST_SPRING_BREAK_NAME
    assert events[0]["start"].isoformat() == TEST_SPRING_BREAK_START
    assert events[0]["end"].isoformat() == TEST_SPRING_BREAK_END
    assert events[0]["description"] == TEST_SPRING_BREAK_DESCRIPTION

    assert events[1]["summary"] == TEST_SUMMER_HOLIDAY_NAME
    assert events[1]["start"].isoformat() == TEST_SUMMER_HOLIDAY_START
    assert events[1]["end"].isoformat() == TEST_SUMMER_HOLIDAY_END
    assert events[1]["description"] == TEST_SUMMER_HOLIDAY_DESCRIPTION


def test_calendar_available_with_coordinator() -> None:
    """Test calendar availability with coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True

    entity = SchoolHolidaysCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    assert entity.available is True


def test_calendar_unavailable_with_failed_coordinator() -> None:
    """Test calendar availability with failed coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = False

    entity = SchoolHolidaysCalendarEntity(
        coordinator, TEST_CALENDAR_NAME, TEST_COUNTRY, TEST_REGION
    )

    assert entity.available is False
