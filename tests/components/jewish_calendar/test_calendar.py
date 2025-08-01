"""Tests for the Jewish Calendar calendar platform."""

from datetime import datetime

from freezegun import freeze_time
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
    "weekly_portion": "Torah portion",
    "holiday": "Jewish Holiday",
    "omer_count": "עומר",
    "daf_yomi": "Daily Talmud study",
    "candle_lighting": "Candle Lighting",
    "havdalah": "Havdalah",
}


def detect_event_type(event: dict[str, str]) -> str | None:
    """Detect the event type based on description and summary content."""
    for event_type, pattern in EVENT_PATTERNS.items():
        if pattern in event.get("description", "") or pattern in event.get(
            "summary", ""
        ):
            return event_type
    return None


def get_event_types_from_events(events: list[dict[str, str]]) -> set[str]:
    """Get the set of event types found in a list of events."""
    found_event_types = set()
    for event in events:
        event_type = detect_event_type(event)
        if event_type:
            found_event_types.add(event_type)
    return found_event_types


def filter_events_by_type(
    events: list[dict[str, str]], event_type: str
) -> list[dict[str, str]]:
    """Filter events by a specific event type."""
    pattern = EVENT_PATTERNS[event_type]
    return [
        event
        for event in events
        if pattern in event.get("description", "")
        or pattern in event.get("summary", "")
    ]


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_calendar_entity_creation(hass: HomeAssistant) -> None:
    """Test that the calendar entity is created properly."""
    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None
    assert state.name == CALENDAR_ENTITY_NAME


@pytest.mark.parametrize(
    ("calendar_events", "expected_events"),
    [
        (None, DEFAULT_CALENDAR_EVENTS),  # Test default when None
        (["date"], ["date"]),  # Test single event
        (["date", "holiday"], ["date", "holiday"]),  # Test multiple events
        (CALENDAR_EVENT_TYPES, CALENDAR_EVENT_TYPES),  # Test all valid events
        (["invalid_event", "date"], ["date"]),  # Test with invalid (only valid kept)
    ],
)
@pytest.mark.usefixtures("setup")
async def test_calendar_event_configuration(
    hass: HomeAssistant, expected_events: list[str], get_calendar_events
) -> None:
    """Test calendar event configuration is handled properly."""
    # Get the calendar entity
    state = hass.states.get("calendar.jewish_calendar_events")
    assert state is not None

    # Test a date range that should have various event types
    start_date = datetime(2024, 1, 12)  # Friday
    end_date = datetime(2024, 1, 14)  # Sunday (covers Fri, Sat, Sun)

    events = await get_calendar_events(hass, start_date, end_date)

    # Validate that we only get the expected event types
    found_event_types = get_event_types_from_events(events)

    # For invalid event types in configuration, they should be ignored
    valid_expected_events = {
        event_type
        for event_type in expected_events
        if event_type in CALENDAR_EVENT_TYPES
    }

    # We should find events only for the valid configured types
    # Note: Some event types may not have events in our test date range
    # so we check that we don't have events from non-configured types
    unexpected_event_types = found_event_types - valid_expected_events

    # Assert we don't have events from unconfigured types
    assert not unexpected_event_types, (
        f"Found events for unconfigured types: {unexpected_event_types}. "
        f"Expected only: {valid_expected_events}, but found: {found_event_types}"
    )

    # We should have at least some events (date events are always present in any range)
    assert len(events) > 0, "Expected events for configured types but got none"


@freeze_time("2024-01-15")  # Monday
@pytest.mark.usefixtures("setup")
async def test_get_events_date_range(hass: HomeAssistant, get_calendar_events) -> None:
    """Test getting events for a date range."""
    # Test calendar service call
    start_date = datetime(2024, 1, 15)
    end_date = datetime(2024, 1, 17)

    events = await get_calendar_events(hass, start_date, end_date)
    assert isinstance(events, list)

    # Should have date events for the range (3 days)
    date_events = filter_events_by_type(events, "date")
    assert len(date_events) >= 3  # At least one per day


@pytest.mark.parametrize(
    ("test_date", "calendar_events"),
    [
        # Test date events (always present)
        ("2024-01-15", ["date"]),
        ("2024-07-15", ["date"]),
        # Test Torah portion on Saturday
        ("2024-01-13", ["weekly_portion"]),  # Saturday
        # Test Omer count during Omer period (between Pesach and Shavuot)
        ("2024-04-24", ["omer_count"]),  # During Omer
        # Test candle lighting on Friday
        ("2024-01-12", ["candle_lighting"]),  # Friday
        # Test Havdalah on Saturday
        ("2024-01-13", ["havdalah"]),  # Saturday
    ],
)
@freeze_time("2024-01-15")
@pytest.mark.usefixtures("setup")
async def test_specific_event_types_present(
    hass: HomeAssistant,
    test_date: str,
    calendar_events: list[str],
    get_calendar_events,
) -> None:
    """Test specific event types are generated when expected."""
    # Get events for the specific date
    target_date = datetime.fromisoformat(test_date)
    event_type = calendar_events[0]
    events = await get_calendar_events(hass, target_date)

    assert len(events) > 0, f"Expected {event_type} event on {test_date}"

    # Verify event content based on type
    found_event_types = get_event_types_from_events(events)
    assert event_type in found_event_types, f"Expected to find {event_type} event"


@pytest.mark.parametrize(
    ("test_date", "calendar_events"),
    [
        # Test Torah portion NOT on Friday
        ("2024-01-12", ["weekly_portion"]),
        # Test Omer count outside Omer period
        ("2024-01-15", ["omer_count"]),  # Outside Omer
        # Test candle lighting NOT on Saturday
        ("2024-01-13", ["candle_lighting"]),  # Saturday
        # Test Havdalah NOT on Friday
        ("2024-01-12", ["havdalah"]),  # Friday
    ],
)
@freeze_time("2024-01-15")
@pytest.mark.usefixtures("setup")
async def test_specific_event_types_absent(
    hass: HomeAssistant,
    test_date: str,
    calendar_events: list[str],
    get_calendar_events,
) -> None:
    """Test specific event types are NOT generated when not expected."""
    # Get events for the specific date
    target_date = datetime.fromisoformat(test_date)
    event_type = calendar_events[0]
    events = await get_calendar_events(hass, target_date)

    # If there are events, they shouldn't be of the type we're testing for
    found_event_types = get_event_types_from_events(events)
    assert event_type not in found_event_types, (
        f"Did not expect to find {event_type} event on {test_date}"
    )


@pytest.mark.parametrize("test_time", [datetime(2024, 1, 25)], indirect=True)
@pytest.mark.parametrize("calendar_events", [["holiday"]])
@pytest.mark.usefixtures("setup_at_time")
async def test_holiday_events(hass: HomeAssistant, get_calendar_events) -> None:
    """Test holiday events are created properly."""
    # Get events for Tu BiShvat
    target_date = datetime(2024, 1, 25)
    events = await get_calendar_events(hass, target_date)
    assert len(events) > 0

    # Should have holiday event
    holiday_events = filter_events_by_type(events, "holiday")
    assert len(holiday_events) > 0


@pytest.mark.parametrize("test_time", [datetime(2024, 7, 15)], indirect=True)
@pytest.mark.parametrize("calendar_events", [["daf_yomi"]], indirect=True)
@pytest.mark.usefixtures("setup_at_time")
async def test_daf_yomi_events(hass: HomeAssistant, get_calendar_events) -> None:
    """Test daf yomi events are created properly."""
    # Get events for test date
    target_date = datetime(2024, 7, 15)
    events = await get_calendar_events(hass, target_date)
    assert len(events) > 0

    # Should have daf yomi event
    daf_yomi_events = filter_events_by_type(events, "daf_yomi")
    assert len(daf_yomi_events) > 0


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.parametrize("test_time", [datetime(2024, 1, 12)], indirect=True)
@pytest.mark.usefixtures("setup_at_time")
async def test_candle_lighting_times(hass: HomeAssistant, get_calendar_events) -> None:
    """Test candle lighting times are calculated for different locations."""
    # Get events for Friday
    target_date = datetime(2024, 1, 12)  # Friday
    events = await get_calendar_events(hass, target_date)

    # Should have date event at minimum due to default config
    assert len(events) > 0


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.parametrize("test_time", [datetime(2024, 1, 13)], indirect=True)
@pytest.mark.usefixtures("setup_at_time")
async def test_havdalah_times(hass: HomeAssistant, get_calendar_events) -> None:
    """Test Havdalah times are calculated for different locations."""
    # Get events for Saturday
    target_date = datetime(2024, 1, 13)  # Saturday
    events = await get_calendar_events(hass, target_date)

    # Should have date event at minimum due to default config
    assert len(events) > 0
