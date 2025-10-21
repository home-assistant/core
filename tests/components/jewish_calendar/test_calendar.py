"""Tests for the Jewish Calendar calendar platform."""

import datetime as dt

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.jewish_calendar.const import (
    CALENDAR_EVENT_TYPES,
    DEFAULT_CALENDAR_EVENTS,
)
from homeassistant.core import HomeAssistant

CALENDAR_ENTITY_ID = "calendar.jewish_calendar_events"
CALENDAR_ENTITY_NAME = "Jewish Calendar Events"


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_calendar_entity_creation(hass: HomeAssistant) -> None:
    """Test that the calendar entity is created properly."""
    state = hass.states.get(CALENDAR_ENTITY_ID)
    assert state is not None
    assert state.name == CALENDAR_ENTITY_NAME

    # Verify essential attributes
    assert state.attributes["friendly_name"] == CALENDAR_ENTITY_NAME
    assert "message" in state.attributes
    assert "start_time" in state.attributes
    assert "end_time" in state.attributes
    assert "all_day" in state.attributes
    assert "description" in state.attributes

    # Hebrew date event should always be present and all-day
    assert state.attributes["all_day"] is True
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
    state = hass.states.get(CALENDAR_ENTITY_ID)
    assert state is not None

    # Get events for a date range that should have various event types
    start_date = dt.date(2024, 1, 12)  # Friday
    end_date = dt.date(2024, 1, 14)  # Sunday
    events = await get_calendar_events(hass, start_date, end_date)

    # Filter out invalid event types from expected
    valid_expected_events = {
        event_type
        for event_type in expected_events
        if event_type in CALENDAR_EVENT_TYPES
    }

    # Extract actual event types from descriptions
    found_event_types = set()
    for event in events:
        description = event.get("description", "")
        if description.startswith("Hebrew date"):
            found_event_types.add("date")
        elif description.startswith("Parshat Hashavua"):
            found_event_types.add("weekly_portion")
        elif description.startswith("Jewish Holiday"):
            found_event_types.add("holiday")
        elif description.startswith("Sefirat HaOmer"):
            found_event_types.add("omer_count")
        elif description.startswith("Daf Yomi"):
            found_event_types.add("daf_yomi")
        elif description.startswith("Candle lighting time"):
            found_event_types.add("candle_lighting")
        elif description.startswith("Havdalah time"):
            found_event_types.add("havdalah")

    # Should not have events from unconfigured types
    unexpected_event_types = found_event_types - valid_expected_events
    assert not unexpected_event_types, (
        f"Found events for unconfigured types: {unexpected_event_types}"
    )

    # Should have at least some events
    assert len(events) > 0


@pytest.mark.parametrize("test_date", [dt.date(2024, 1, 15)])
@pytest.mark.usefixtures("setup_at_time")
async def test_get_events_date_range(
    hass: HomeAssistant, test_date: dt.date, get_calendar_events
) -> None:
    """Test getting events for a date range."""
    end_date = dt.date(2024, 1, 17)
    events = await get_calendar_events(hass, test_date, end_date)
    assert isinstance(events, list)
    assert len(events) >= 3  # At least date events for 3 days

    # All events should have required fields
    for event in events:
        assert "summary" in event
        assert "description" in event
        assert "start" in event
        assert "end" in event


# Test specific event types with snapshot comparison
@pytest.mark.parametrize(
    ("test_date", "calendar_events", "location_data"),
    [
        # Date events (always present)
        (dt.date(2024, 1, 15), ["date"], "New York"),
        (dt.date(2024, 1, 15), ["date"], "Jerusalem"),
        # Weekly portion (Shabbat)
        (dt.date(2024, 9, 7), ["weekly_portion"], "New York"),
        # Holiday (Purim 2024)
        (dt.date(2024, 3, 25), ["holiday"], "Jerusalem"),
        # Omer count (during Omer period)
        (dt.date(2024, 4, 24), ["omer_count"], "New York"),
        # Daf Yomi
        (dt.date(2024, 7, 15), ["daf_yomi"], "Jerusalem"),
        # Candle lighting (Friday)
        (dt.date(2024, 1, 12), ["candle_lighting"], "New York"),
        (dt.date(2024, 1, 12), ["candle_lighting"], "Jerusalem"),
        # Havdalah (Saturday)
        (dt.date(2024, 1, 13), ["havdalah"], "New York"),
        (dt.date(2024, 1, 13), ["havdalah"], "Jerusalem"),
        # Multiple event types
        (
            dt.date(2024, 1, 12),
            ["date", "weekly_portion", "candle_lighting"],
            "New York",
        ),
        (dt.date(2024, 1, 13), ["date", "weekly_portion", "havdalah"], "Jerusalem"),
    ],
    indirect=["location_data"],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_event_types_snapshot(
    hass: HomeAssistant,
    test_date: dt.date,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test various event types with snapshot comparison."""
    events = await get_calendar_events(hass, test_date)
    assert events == snapshot


# Test specific event presence/absence scenarios
@pytest.mark.parametrize(
    ("test_date", "calendar_events", "expected_present", "expected_absent"),
    [
        # Holiday on Purim
        (dt.date(2024, 3, 25), ["holiday"], ["holiday"], []),
        # No holiday on random date
        (dt.date(2024, 6, 15), ["holiday"], [], ["holiday"]),
        # Omer during period
        (dt.date(2024, 4, 24), ["omer_count"], ["omer_count"], []),
        # No Omer outside period
        (dt.date(2024, 1, 15), ["omer_count"], [], ["omer_count"]),
        # Candle lighting on Friday
        (dt.date(2024, 1, 12), ["candle_lighting"], ["candle_lighting"], []),
        # No candle lighting on Saturday
        (dt.date(2024, 1, 13), ["candle_lighting"], [], ["candle_lighting"]),
        # Havdalah on Saturday
        (dt.date(2024, 1, 13), ["havdalah"], ["havdalah"], []),
        # No havdalah on Friday
        (dt.date(2024, 1, 12), ["havdalah"], [], ["havdalah"]),
    ],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_event_presence_and_absence(
    hass: HomeAssistant,
    test_date: dt.date,
    get_calendar_events,
    expected_present: list[str],
    expected_absent: list[str],
) -> None:
    """Test that specific event types are present or absent as expected."""
    events = await get_calendar_events(hass, test_date)

    # Extract event types from descriptions
    found_event_types = set()
    for event in events:
        description = event.get("description", "")
        if description.startswith("Hebrew date"):
            found_event_types.add("date")
        elif description.startswith("Parshat Hashavua"):
            found_event_types.add("weekly_portion")
        elif description.startswith("Jewish Holiday"):
            found_event_types.add("holiday")
        elif description.startswith("Sefirat HaOmer"):
            found_event_types.add("omer_count")
        elif description.startswith("Daf Yomi"):
            found_event_types.add("daf_yomi")
        elif description.startswith("Candle lighting time"):
            found_event_types.add("candle_lighting")
        elif description.startswith("Havdalah time"):
            found_event_types.add("havdalah")

    # Check expected present
    for event_type in expected_present:
        assert event_type in found_event_types, (
            f"Expected to find {event_type} event on {test_date}"
        )

    # Check expected absent
    for event_type in expected_absent:
        assert event_type not in found_event_types, (
            f"Did not expect to find {event_type} event on {test_date}"
        )


# Validate all-day vs timed events
@pytest.mark.parametrize(
    ("test_date", "calendar_events", "location_data"),
    [
        # All-day events
        (dt.date(2024, 1, 15), ["date"], "New York"),
        (dt.date(2024, 9, 7), ["weekly_portion"], "Jerusalem"),
        (dt.date(2024, 3, 25), ["holiday"], "New York"),
        (dt.date(2024, 4, 24), ["omer_count"], "Jerusalem"),
        (dt.date(2024, 7, 15), ["daf_yomi"], "New York"),
        # Timed events
        (dt.date(2024, 1, 12), ["candle_lighting"], "New York"),
        (dt.date(2024, 1, 13), ["havdalah"], "Jerusalem"),
    ],
    indirect=["location_data"],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_event_timing_format(
    hass: HomeAssistant,
    test_date: dt.date,
    get_calendar_events,
    calendar_events: list[str],
) -> None:
    """Test that all-day and timed events have correct format."""
    events = await get_calendar_events(hass, test_date)
    assert len(events) > 0, f"No events found for {test_date}"

    for event in events:
        event_type = calendar_events[0]  # We're testing one type at a time

        # All-day events
        if event_type in [
            "date",
            "weekly_portion",
            "holiday",
            "omer_count",
            "daf_yomi",
        ]:
            # Start should be a date string
            assert isinstance(event["start"], str)
            assert "T" not in event["start"], (
                "All-day events should not have time component"
            )
            # End should be next day
            start_date = dt.date.fromisoformat(event["start"])
            end_date = dt.date.fromisoformat(event["end"])
            assert (end_date - start_date).days == 1

        # Timed events
        elif event_type in ["candle_lighting", "havdalah"]:
            # Should have datetime with timezone
            assert isinstance(event["start"], str)
            assert "T" in event["start"], "Timed events should have time component"
            # For instant events, start == end
            assert event["start"] == event["end"]
