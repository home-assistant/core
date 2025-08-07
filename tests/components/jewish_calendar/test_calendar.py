"""Tests for the Jewish Calendar calendar platform."""

import datetime as dt
import re
from typing import Any

import pytest

from homeassistant.components.jewish_calendar.const import (
    CALENDAR_EVENT_TYPES,
    DEFAULT_CALENDAR_EVENTS,
)
from homeassistant.core import HomeAssistant

# Test constants
CALENDAR_ENTITY_NAME = "Jewish Calendar Events"

# Event detection patterns
EVENT_PATTERNS = {
    "date": "Hebrew date",
    "weekly_portion": "Parshat Hashavua",
    "holiday": "Jewish Holiday",
    "omer_count": "Sefirat HaOmer",
    "daf_yomi": "Daf Yomi",
    "candle_lighting": "Candle lighting time",
    "havdalah": "Havdalah time",
}

# Event type configurations for testing
EVENT_TYPE_CONFIGS = {
    "date": {
        "is_all_day": True,
        "content_checks": ["Hebrew date:"],
        "test_dates": [dt.date(2024, 1, 15), dt.date(2024, 1, 16)],
        "absent_dates": [],
    },
    "weekly_portion": {
        "description_pattern": r"Parshat Hashavua:",
        "is_all_day": True,
        "content_checks": ["Parshat Hashavua:"],
        "test_dates": [dt.date(2024, 9, 8)],  # A Shabbat
        "absent_dates": [],  # Weekly portion appears all week long
    },
    "holiday": {
        "description_pattern": r"Jewish Holiday:",
        "is_all_day": True,
        "content_checks": ["Jewish Holiday:"],
        "test_dates": [dt.date(2024, 3, 25)],  # Purim 2024
        "absent_dates": [dt.date(2024, 6, 15)],  # Random date
    },
    "omer_count": {
        "is_all_day": True,
        "content_checks": ["Sefirat HaOmer:"],
        "test_dates": [dt.date(2024, 4, 24)],  # During Omer period
        "absent_dates": [dt.date(2024, 1, 15)],  # Outside Omer period
    },
    "daf_yomi": {
        "is_all_day": True,
        "content_checks": ["Daf Yomi:"],
        "test_dates": [dt.date(2024, 7, 15)],
        "absent_dates": [],
    },
    "candle_lighting": {
        "description_pattern": r"Candle lighting time: \d{1,2}:\d{2}",
        "is_all_day": False,
        "content_checks": ["Candle Lighting", "Candle lighting time:"],
        "test_dates": [dt.date(2024, 1, 12)],  # Friday
        "absent_dates": [dt.date(2024, 1, 13)],  # Saturday (no candle lighting)
        # Note: times are in UTC, so local evening times may appear as early hours
    },
    "havdalah": {
        "description_pattern": r"Havdalah time: \d{1,2}:\d{2}",
        "is_all_day": False,
        "content_checks": ["Havdalah", "Havdalah time:"],
        "test_dates": [dt.date(2024, 1, 13)],  # Saturday
        "absent_dates": [dt.date(2024, 1, 12)],  # Friday (no havdalah)
        # Note: times are in UTC, so local evening times may appear as early hours
    },
}


def detect_event_type(event: dict[str, Any]) -> str | None:
    """Detect the event type based on description and summary content."""
    for event_type, pattern in EVENT_PATTERNS.items():
        if event.get("description", "").startswith(pattern):
            return event_type
    return None


def get_event_types_from_events(events: list[dict[str, Any]]) -> set[str]:
    """Get the set of event types found in a list of events."""
    return {event_type for event in events if (event_type := detect_event_type(event))}


def filter_events_by_type(
    events: list[dict[str, Any]], event_type: str
) -> list[dict[str, Any]]:
    """Filter events by a specific event type."""
    pattern = EVENT_PATTERNS[event_type]
    return [
        event for event in events if event.get("description", "").startswith(pattern)
    ]


def extract_event_date(event: dict[str, Any]) -> dt.date:
    """Extract date from event start field, handling multiple formats."""
    start = event["start"]
    if isinstance(start, str):
        if "T" in start:  # ISO datetime string
            return dt.datetime.fromisoformat(start).date()
        return dt.date.fromisoformat(start)  # ISO date string
    if isinstance(start, dict):
        if "date" in start:
            return dt.date.fromisoformat(start["date"])
        if "dateTime" in start:
            return dt.datetime.fromisoformat(start["dateTime"]).date()
    raise ValueError(f"Unsupported event start format: {start}")


def validate_event_structure(event: dict[str, Any]) -> None:
    """Validate that an event has the required structure."""
    required_fields = ["summary", "description", "start", "end"]
    for field in required_fields:
        assert field in event, f"Event missing required field: {field}"


def validate_event_content(event: dict[str, Any], event_type: str) -> None:
    """Validate event content based on type configuration."""
    config = EVENT_TYPE_CONFIGS[event_type]

    # Check description pattern (regex)
    if "description_pattern" in config:
        pattern = config["description_pattern"]
        assert re.match(pattern, event["description"]), (
            f"Description '{event['description']}' doesn't match pattern '{pattern}'"
        )

    # Check content (simple string contains checks)
    for content_check in config.get("content_checks", []):
        assert content_check in event["summary"] or content_check in event.get(
            "description", ""
        )


def validate_event_timing(
    event: dict[str, Any], event_type: str, target_date: dt.date
) -> None:
    """Validate event timing based on type configuration."""
    config = EVENT_TYPE_CONFIGS[event_type]

    if config["is_all_day"]:
        # All-day events
        if isinstance(event["start"], str):
            assert event["start"] == target_date.isoformat()
            expected_end = (target_date + dt.timedelta(days=1)).isoformat()
            assert event["end"] == expected_end
        elif isinstance(event["start"], dict) and "date" in event["start"]:
            assert event["start"]["date"] == target_date.isoformat()
            expected_end = (target_date + dt.timedelta(days=1)).isoformat()
            assert event["end"]["date"] == expected_end
            # Should not have dateTime for all-day events
            assert "dateTime" not in event["start"]
            assert "dateTime" not in event["end"]
    else:
        # Timed events
        event_date = extract_event_date(event)
        # Allow ±1 day tolerance for timezone/Hebrew calendar logic
        assert abs((event_date - target_date).days) <= 1

        # Check time range if specified
        if config.get("time_range"):
            start_time = dt.datetime.fromisoformat(event["start"])
            min_hour, max_hour = config["time_range"]
            assert min_hour <= start_time.hour <= max_hour

            # For instant events (candle lighting, havdalah), start == end
            end_time = dt.datetime.fromisoformat(event["end"])
            assert start_time == end_time


@pytest.fixture
def event_validator():
    """Fixture providing event validation functions."""
    return {
        "structure": validate_event_structure,
        "content": validate_event_content,
        "timing": validate_event_timing,
        "extract_date": extract_event_date,
    }


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_calendar_entity_creation(hass: HomeAssistant) -> None:
    """Test that the calendar entity is created properly."""
    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None
    assert state.name == CALENDAR_ENTITY_NAME

    # Verify the entity has the expected attributes
    attributes = state.attributes
    assert "friendly_name" in attributes
    assert attributes["friendly_name"] == CALENDAR_ENTITY_NAME

    # Check that the entity has a current event (Hebrew date should always be present)
    required_attrs = ["message", "start_time", "end_time", "all_day", "description"]
    for attr in required_attrs:
        assert attr in attributes

    # Hebrew date event should be all-day
    assert attributes["all_day"] is True

    # The entity should be "on" when there's a current event
    assert state.state == "on"


@pytest.mark.parametrize(
    ("calendar_events", "expected_events"),
    [
        (None, DEFAULT_CALENDAR_EVENTS),
        (["date"], ["date"]),
        (["date", "holiday"], ["date", "holiday"]),
        (CALENDAR_EVENT_TYPES, CALENDAR_EVENT_TYPES),
        (["invalid_event", "date"], ["date"]),
    ],
)
@pytest.mark.usefixtures("setup")
async def test_calendar_event_configuration(
    hass: HomeAssistant, expected_events: list[str], get_calendar_events
) -> None:
    """Test calendar event configuration is handled properly."""
    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None

    # Test a date range that should have various event types
    start_date = dt.date(2024, 1, 12)  # Friday
    end_date = dt.date(2024, 1, 14)  # Sunday

    events = await get_calendar_events(hass, start_date, end_date)
    found_event_types = get_event_types_from_events(events)

    # Filter out invalid event types
    valid_expected_events = {
        event_type
        for event_type in expected_events
        if event_type in CALENDAR_EVENT_TYPES
    }

    # We should not have events from unconfigured types
    unexpected_event_types = found_event_types - valid_expected_events
    assert not unexpected_event_types, (
        f"Found events for unconfigured types: {unexpected_event_types}"
    )

    # Should have at least some events
    assert len(events) > 0


@pytest.mark.parametrize("test_date", [dt.date(2024, 1, 15)])
@pytest.mark.usefixtures("setup_at_time")
async def test_get_events_date_range(
    hass: HomeAssistant, test_date: dt.date, get_calendar_events, event_validator
) -> None:
    """Test getting events for a date range."""
    end_date = dt.date(2024, 1, 17)
    events = await get_calendar_events(hass, test_date, end_date)
    assert isinstance(events, list)

    # Should have date events for the range
    date_events = filter_events_by_type(events, "date")
    assert len(date_events) >= 3  # At least one per day

    # Validate each date event
    for date_event in date_events:
        event_validator["structure"](date_event)
        event_validator["content"](date_event, "date")

        # Verify events are within the requested date range
        event_date = event_validator["extract_date"](date_event)
        assert test_date <= event_date <= end_date


# Parametrized test for event presence
@pytest.mark.parametrize(
    ("event_type", "test_date", "calendar_events"),
    [
        (event_type, test_date, [event_type])
        for event_type, config in EVENT_TYPE_CONFIGS.items()
        for test_date in config.get("test_dates", [])
    ],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_event_type_present(
    hass: HomeAssistant,
    event_type: str,
    test_date: dt.date,
    get_calendar_events,
    event_validator,
) -> None:
    """Test that specific event types are present when expected."""
    events = await get_calendar_events(hass, test_date)
    assert len(events) > 0, f"Expected {event_type} event on {test_date}"

    # Verify the expected event type is present
    found_event_types = get_event_types_from_events(events)
    assert event_type in found_event_types, f"Expected to find {event_type} event"

    # Get and validate the specific events
    type_events = filter_events_by_type(events, event_type)
    assert len(type_events) > 0, f"No {event_type} events found"

    for event in type_events:
        event_validator["structure"](event)
        event_validator["content"](event, event_type)
        event_validator["timing"](event, event_type, test_date)


# Parametrized test for event absence
@pytest.mark.parametrize(
    ("event_type", "test_date", "calendar_events"),
    [
        (event_type, absent_date, [event_type])
        for event_type, config in EVENT_TYPE_CONFIGS.items()
        for absent_date in config.get("absent_dates", [])
    ],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_event_type_absent(
    hass: HomeAssistant, event_type: str, test_date: dt.date, get_calendar_events
) -> None:
    """Test that specific event types are absent when not expected."""
    events = await get_calendar_events(hass, test_date)

    # The specified event type should not be present
    found_event_types = get_event_types_from_events(events)
    assert event_type not in found_event_types, (
        f"Did not expect to find {event_type} event on {test_date}"
    )


# Parametrized test for location-based events (candle lighting and havdalah)
@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.parametrize(
    ("event_type", "test_date", "calendar_events"),
    [
        ("candle_lighting", dt.date(2024, 1, 12), ["candle_lighting"]),  # Friday
        ("havdalah", dt.date(2024, 1, 13), ["havdalah"]),  # Saturday
    ],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_location_based_events(
    hass: HomeAssistant,
    event_type: str,
    test_date: dt.date,
    get_calendar_events,
    event_validator,
) -> None:
    """Test location-based timed events (candle lighting and havdalah)."""
    events = await get_calendar_events(hass, test_date)
    assert len(events) > 0, f"No events found for {test_date}"

    # Find the specific event type
    type_events = filter_events_by_type(events, event_type)
    assert len(type_events) == 1, f"Expected exactly one {event_type} event"

    event = type_events[0]
    event_validator["structure"](event)
    event_validator["content"](event, event_type)
    event_validator["timing"](event, event_type, test_date)
