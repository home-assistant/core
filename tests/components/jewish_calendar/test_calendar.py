"""Tests for the Jewish Calendar calendar platform."""

import datetime as dt
from datetime import datetime

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
    "candle_lighting": "Candle lighting time",  # Fixed: lowercase "lighting" and includes "time"
    "havdalah": "Havdalah time",  # Fixed: includes "time"
}


def detect_event_type(event: dict[str, str]) -> str | None:
    """Detect the event type based on description and summary content."""
    for event_type, pattern in EVENT_PATTERNS.items():
        if event.get("description", "").startswith(pattern):
            return event_type
    return None


def get_event_types_from_events(events: list[dict[str, str]]) -> set[str]:
    """Get the set of event types found in a list of events."""
    return {event_type for event in events if (event_type := detect_event_type(event))}


def filter_events_by_type(
    events: list[dict[str, str]], event_type: str
) -> list[dict[str, str]]:
    """Filter events by a specific event type."""
    pattern = EVENT_PATTERNS[event_type]
    return [
        event for event in events if event.get("description", "").startswith(pattern)
    ]


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
    assert "message" in attributes
    assert "start_time" in attributes
    assert "end_time" in attributes
    assert "all_day" in attributes
    assert "description" in attributes

    # Hebrew date event should be all-day
    assert attributes["all_day"] is True

    # The entity should be "on" when there's a current event
    assert state.state == "on"


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
    start_date = dt.date(2024, 1, 12)  # Friday
    end_date = dt.date(2024, 1, 14)  # Sunday (covers Fri, Sat, Sun)

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


@pytest.mark.parametrize("test_date", [dt.date(2024, 1, 15)])
@pytest.mark.usefixtures("setup_at_time")
async def test_get_events_date_range(
    hass: HomeAssistant, test_date: dt.date, get_calendar_events
) -> None:
    """Test getting events for a date range."""
    end_date = dt.date(2024, 1, 17)

    events = await get_calendar_events(hass, test_date, end_date)
    assert isinstance(events, list)

    # Should have date events for the range (3 days)
    date_events = filter_events_by_type(events, "date")
    assert len(date_events) >= 3  # At least one per day

    # Verify date events have proper structure
    for date_event in date_events:
        assert "summary" in date_event
        assert "description" in date_event
        assert "start" in date_event
        assert "end" in date_event

        # Verify it's a date event
        assert date_event["description"].startswith("Hebrew date")

        # Date events should be all-day events (start/end are date strings)
        assert isinstance(date_event["start"], str)
        assert isinstance(date_event["end"], str)

        # Verify date format is ISO date (YYYY-MM-DD)
        datetime.strptime(date_event["start"], "%Y-%m-%d")
        datetime.strptime(date_event["end"], "%Y-%m-%d")

    # Verify events are within the requested date range
    for event in events:
        if isinstance(event["start"], str):
            # All-day event with date string
            event_date = dt.date.fromisoformat(event["start"])
        elif isinstance(event["start"], dict) and "date" in event["start"]:
            # Timed event with date dict
            event_date = dt.date.fromisoformat(event["start"]["date"])
        else:
            # ISO datetime string
            event_datetime = dt.datetime.fromisoformat(event["start"])
            event_date = event_datetime.date()

        assert test_date <= event_date <= end_date, (
            f"Event date {event_date} not in range {test_date} to {end_date}"
        )


@pytest.mark.parametrize(
    ("test_date", "calendar_events"),
    [
        # Test date events (always present)
        (dt.date(2024, 1, 15), ["date"]),
        (dt.date(2024, 7, 15), ["date"]),
        # Test Torah portion on Saturday
        (dt.date(2024, 1, 13), ["weekly_portion"]),  # Saturday
        # Test Omer count during Omer period (between Pesach and Shavuot)
        (dt.date(2024, 4, 24), ["omer_count"]),  # During Omer
        # Test candle lighting on Friday
        (dt.date(2024, 1, 12), ["candle_lighting"]),  # Friday
        # Test Havdalah on Saturday
        (dt.date(2024, 1, 13), ["havdalah"]),  # Saturday
    ],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_specific_event_types_present(
    hass: HomeAssistant,
    test_date: dt.date,
    calendar_events: list[str],
    get_calendar_events,
) -> None:
    """Test specific event types are generated when expected."""
    # Get events for the specific date
    event_type = calendar_events[0]
    events = await get_calendar_events(hass, test_date)

    assert len(events) > 0, f"Expected {event_type} event on {test_date}"

    # Verify event content based on type
    found_event_types = get_event_types_from_events(events)
    assert event_type in found_event_types, f"Expected to find {event_type} event"

    # Get the specific events of this type for additional validation
    type_events = filter_events_by_type(events, event_type)
    assert len(type_events) > 0, f"No {event_type} events found"

    # Verify event structure for each type
    for event in type_events:
        assert "summary" in event
        assert "description" in event
        assert "start" in event
        assert "end" in event

        # Verify the event is on the correct date
        if event_type in ["candle_lighting", "havdalah"]:
            # Timed events - should have ISO datetime strings
            # Note: These events might occur on adjacent dates due to Hebrew calendar/timezone logic
            if isinstance(event["start"], str):
                # ISO datetime string format
                event_datetime = dt.datetime.fromisoformat(event["start"])
                event_date = event_datetime.date()
                # Allow events within 1 day of test date for timezone/Hebrew calendar reasons
                assert abs((event_date - test_date).days) <= 1, (
                    f"{event_type} event date {event_date} not within 1 day of {test_date}"
                )
            elif isinstance(event["start"], dict) and "dateTime" in event["start"]:
                # Event with dateTime dict
                event_datetime = dt.datetime.fromisoformat(event["start"]["dateTime"])
                event_date = event_datetime.date()
                # Allow events within 1 day of test date for timezone/Hebrew calendar reasons
                assert abs((event_date - test_date).days) <= 1, (
                    f"{event_type} event date {event_date} not within 1 day of {test_date}"
                )
            else:
                pytest.fail(f"Unexpected timed event format: {event['start']}")
        elif isinstance(event["start"], str):
            # All-day events with date string format - start should be test_date
            assert event["start"] == test_date.isoformat()
            # End date is typically the next day for all-day events
            expected_end = (test_date + dt.timedelta(days=1)).isoformat()
            assert event["end"] == expected_end
        elif isinstance(event["start"], dict) and "date" in event["start"]:
            # All-day events with date dict
            assert event["start"]["date"] == test_date.isoformat()
            expected_end = (test_date + dt.timedelta(days=1)).isoformat()
            assert event["end"]["date"] == expected_end
        else:
            pytest.fail(f"Unexpected event format: {event['start']}")


@pytest.mark.parametrize(
    ("test_date", "calendar_events"),
    [
        # Test Omer count outside Omer period
        (dt.date(2024, 1, 15), ["omer_count"]),  # Outside Omer
        # Test candle lighting NOT on Friday (Saturday shouldn't have candle lighting)
        (dt.date(2024, 1, 13), ["candle_lighting"]),  # Saturday
        # Test Havdalah NOT on Friday (Friday shouldn't have Havdalah)
        (dt.date(2024, 1, 12), ["havdalah"]),  # Friday
    ],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_specific_event_types_absent(
    hass: HomeAssistant,
    test_date: dt.date,
    calendar_events: list[str],
    get_calendar_events,
) -> None:
    """Test specific event types are NOT generated when not expected."""
    # Get events for the specific date
    event_type = calendar_events[0]
    events = await get_calendar_events(hass, test_date)

    # If there are events, they shouldn't be of the type we're testing for
    found_event_types = get_event_types_from_events(events)
    assert event_type not in found_event_types, (
        f"Did not expect to find {event_type} event on {test_date}"
    )


@pytest.mark.parametrize("test_time", [dt.date(2024, 1, 25)])
@pytest.mark.parametrize("calendar_events", [["holiday"]])
@pytest.mark.usefixtures("setup_at_time")
async def test_holiday_events(hass: HomeAssistant, get_calendar_events) -> None:
    """Test holiday events are created properly."""
    # Get events for Tu BiShvat
    target_date = dt.date(2024, 1, 25)
    events = await get_calendar_events(hass, target_date)
    assert len(events) > 0

    # Should have holiday event
    holiday_events = filter_events_by_type(events, "holiday")
    assert len(holiday_events) > 0

    # Verify holiday event structure
    holiday_event = holiday_events[0]
    assert "summary" in holiday_event
    assert "description" in holiday_event
    assert "start" in holiday_event
    assert "end" in holiday_event

    # Verify it's actually a holiday event
    assert holiday_event["description"].startswith("Jewish Holiday")
    # Holiday name could be in Hebrew or English - check for both
    assert (
        "Tu BiShvat" in holiday_event["summary"]
        or 'ט"ו בשבט' in holiday_event["summary"]
        or "Tu B'Shvat" in holiday_event["summary"]
    ), f"Expected Tu BiShvat holiday in summary: {holiday_event['summary']}"

    # Verify the event is on the correct date
    if isinstance(holiday_event["start"], str):
        # All-day event with date string format
        assert holiday_event["start"] == target_date.isoformat()
        expected_end = (target_date + dt.timedelta(days=1)).isoformat()
        assert holiday_event["end"] == expected_end
    elif isinstance(holiday_event["start"], dict) and "date" in holiday_event["start"]:
        # Event with date dict
        assert holiday_event["start"]["date"] == target_date.isoformat()
        expected_end = (target_date + dt.timedelta(days=1)).isoformat()
        assert holiday_event["end"]["date"] == expected_end
    else:
        pytest.fail(f"Unexpected holiday event format: {holiday_event['start']}")

    # Holiday events should be all-day events
    if isinstance(holiday_event["start"], dict):
        # Dict format - should have date, not dateTime
        assert "date" in holiday_event["start"]
        assert "date" in holiday_event["end"]
        assert "dateTime" not in holiday_event["start"]
        assert "dateTime" not in holiday_event["end"]


@pytest.mark.parametrize("test_time", [dt.date(2024, 7, 15)])
@pytest.mark.parametrize("calendar_events", [["daf_yomi"]])
@pytest.mark.usefixtures("setup_at_time")
async def test_daf_yomi_events(hass: HomeAssistant, get_calendar_events) -> None:
    """Test daf yomi events are created properly."""
    # Get events for test date
    target_date = dt.date(2024, 7, 15)
    events = await get_calendar_events(hass, target_date)
    assert len(events) > 0

    # Should have daf yomi event
    daf_yomi_events = filter_events_by_type(events, "daf_yomi")
    assert len(daf_yomi_events) == 1

    daf_yomi_event = daf_yomi_events[0]

    # Verify event structure and content
    assert "summary" in daf_yomi_event
    assert "description" in daf_yomi_event
    assert "start" in daf_yomi_event
    assert "end" in daf_yomi_event

    # Verify it's actually a daf yomi event
    assert daf_yomi_event["description"].startswith("Daf Yomi")

    # Verify the event is on the correct date
    if isinstance(daf_yomi_event["start"], str):
        # All-day event with date string format
        assert daf_yomi_event["start"] == target_date.isoformat()
        expected_end = (target_date + dt.timedelta(days=1)).isoformat()
        assert daf_yomi_event["end"] == expected_end
    elif (
        isinstance(daf_yomi_event["start"], dict) and "date" in daf_yomi_event["start"]
    ):
        # Event with date dict
        assert daf_yomi_event["start"]["date"] == target_date.isoformat()
        expected_end = (target_date + dt.timedelta(days=1)).isoformat()
        assert daf_yomi_event["end"]["date"] == expected_end
    else:
        pytest.fail(f"Unexpected daf yomi event format: {daf_yomi_event['start']}")

    # Daf yomi events should be all-day events
    if isinstance(daf_yomi_event["start"], dict):
        # Dict format - should have date, not dateTime
        assert "date" in daf_yomi_event["start"]
        assert "date" in daf_yomi_event["end"]
        assert "dateTime" not in daf_yomi_event["start"]
        assert "dateTime" not in daf_yomi_event["end"]

    # Summary should contain tractate and page information (in Hebrew or English)
    summary = daf_yomi_event["summary"]
    # Check for English terms or assume Hebrew text is valid daf yomi content
    has_english_terms = any(word in summary for word in ("Daf", "daf", "page"))
    is_hebrew_text = any(
        "\u0590" <= char <= "\u05ff" for char in summary
    )  # Hebrew Unicode range
    assert has_english_terms or is_hebrew_text, (
        f"Expected tractate/page info in summary: {summary}"
    )


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.parametrize("test_date", [dt.date(2024, 1, 12)])
@pytest.mark.parametrize("calendar_events", [["candle_lighting"]])
@pytest.mark.usefixtures("setup_at_time")
async def test_candle_lighting_times(
    hass: HomeAssistant, test_date: dt.date, get_calendar_events
) -> None:
    """Test candle lighting times are calculated for different locations."""
    events = await get_calendar_events(hass, test_date)

    # Should have candle lighting events for Friday
    assert len(events) > 0, f"No events found for {test_date}"

    # Find candle lighting events
    candle_lighting_events = filter_events_by_type(events, "candle_lighting")
    assert len(candle_lighting_events) == 1, (
        f"Expected exactly one candle lighting event, got {len(candle_lighting_events)}"
    )

    candle_event = candle_lighting_events[0]

    # Verify event structure and content
    assert "summary" in candle_event
    assert "description" in candle_event
    assert "start" in candle_event
    assert "end" in candle_event

    # Verify it's actually a candle lighting event
    assert candle_event["description"].startswith("Candle lighting time")
    assert "Candle Lighting" in candle_event["summary"]

    # Verify the event is on the correct date
    start_date = dt.datetime.fromisoformat(candle_event["start"]).date()
    end_date = dt.datetime.fromisoformat(candle_event["end"]).date()
    assert start_date == test_date
    assert end_date == test_date

    # Verify time is present and reasonable (should be in the evening)
    start_time = dt.datetime.fromisoformat(candle_event["start"])
    end_time = dt.datetime.fromisoformat(candle_event["end"])
    assert start_time.hour >= 14  # Should be afternoon/evening (after 2 PM)
    assert start_time.hour <= 22  # Should be before 10 PM
    assert start_time == end_time  # Candle lighting is an instant event


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.parametrize("test_date", [dt.date(2024, 1, 13)])  # Saturday for Havdalah
@pytest.mark.parametrize("calendar_events", [["havdalah"]])
@pytest.mark.usefixtures("setup_at_time")
async def test_havdalah_times(
    hass: HomeAssistant, test_date: dt.date, get_calendar_events
) -> None:
    """Test Havdalah times are calculated for different locations."""
    events = await get_calendar_events(hass, test_date)

    # Should have havdalah events for Saturday
    assert len(events) > 0, f"No events found for {test_date}"

    # Find havdalah events
    havdalah_events = filter_events_by_type(events, "havdalah")
    assert len(havdalah_events) == 1, (
        f"Expected exactly one havdalah event, got {len(havdalah_events)}"
    )

    havdalah_event = havdalah_events[0]

    # Verify event structure and content
    assert "summary" in havdalah_event
    assert "description" in havdalah_event
    assert "start" in havdalah_event
    assert "end" in havdalah_event

    # Verify it's actually a havdalah event
    assert (
        "Havdalah" in havdalah_event["description"]
        or "Havdalah" in havdalah_event["summary"]
    )

    # Verify the event is on the correct date
    start_date = dt.datetime.fromisoformat(havdalah_event["start"]).date()
    end_date = dt.datetime.fromisoformat(havdalah_event["end"]).date()
    assert start_date == test_date
    assert end_date == test_date

    # Verify time is present and reasonable (should be in the evening after sunset)
    start_time = dt.datetime.fromisoformat(havdalah_event["start"])
    end_time = dt.datetime.fromisoformat(havdalah_event["end"])
    assert start_time.hour >= 14  # Should be afternoon/evening
    assert start_time.hour <= 22  # Should be before 10 PM
    assert start_time == end_time  # Havdalah is an instant event
