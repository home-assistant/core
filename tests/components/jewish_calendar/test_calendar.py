"""Tests for the Jewish Calendar calendar platform."""

import datetime as dt

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.jewish_calendar.const import (
    CONF_DAILY_EVENTS,
    CONF_LEARNING_SCHEDULE,
    CONF_YEARLY_EVENTS,
    DailyCalendarEventType,
    YearlyCalendarEventType,
)
from homeassistant.core import HomeAssistant

# Entity IDs for the three calendars
CALENDAR_DAILY_EVENTS = "calendar.jewish_calendar_daily_events"
CALENDAR_LEARNING_SCHEDULE = "calendar.jewish_calendar_learning_schedule"
CALENDAR_YEARLY_EVENTS = "calendar.jewish_calendar_yearly_events"


@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_three_calendar_entities_created(hass: HomeAssistant) -> None:
    """Test that all three calendar entities are created properly."""
    # Check daily events calendar
    state = hass.states.get(CALENDAR_DAILY_EVENTS)
    assert state is not None
    assert state.attributes["friendly_name"] == "Jewish Calendar Daily events"

    # Check learning schedule calendar
    state = hass.states.get(CALENDAR_LEARNING_SCHEDULE)
    assert state is not None
    assert state.attributes["friendly_name"] == "Jewish Calendar Learning schedule"

    # Check yearly events calendar
    state = hass.states.get(CALENDAR_YEARLY_EVENTS)
    assert state is not None
    assert state.attributes["friendly_name"] == "Jewish Calendar Yearly events"


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_daily_events_calendar(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test daily events calendar with exact count and snapshots."""
    start_date = dt.datetime(2024, 1, 15, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_DAILY_EVENTS, start_date)

    # Exact count: DATE + 10 time-based events (Netz and Shkia are not included in default)
    assert len(events) == 11
    assert events == snapshot


@pytest.mark.freeze_time("2024-07-15 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_learning_schedule_calendar(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test learning schedule calendar with exact count and snapshots."""
    start_date = dt.datetime(2024, 7, 15, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_LEARNING_SCHEDULE, start_date)

    # Exact count: 1 Daf Yomi event
    assert len(events) == 1
    assert events == snapshot


@pytest.mark.freeze_time("2024-01-12 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_yearly_events_calendar_friday(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test yearly events calendar on Friday with exact count and snapshots."""
    start_date = dt.datetime(2024, 1, 12, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_YEARLY_EVENTS, start_date)

    # Exact count: Weekly portion + Candle lighting (1 event on Friday - weekly portion only)
    assert len(events) == 1
    assert events == snapshot


@pytest.mark.freeze_time("2024-01-13 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_yearly_events_calendar_saturday(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test yearly events calendar on Saturday with exact count and snapshots."""
    start_date = dt.datetime(2024, 1, 13, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_YEARLY_EVENTS, start_date)

    # Exact count: Weekly portion + Havdalah (1 event on Saturday - weekly portion only)
    assert len(events) == 1
    assert events == snapshot


@pytest.mark.freeze_time("2024-03-25 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_yearly_events_calendar_holiday(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test yearly events calendar on a holiday with exact count and snapshots."""
    start_date = dt.datetime(2024, 3, 25, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_YEARLY_EVENTS, start_date)

    # Exact count: 2 events (Shushan Purim + weekly portion)
    assert len(events) == 2
    assert events == snapshot


@pytest.mark.freeze_time("2024-04-24 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_yearly_events_calendar_omer(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test yearly events calendar during Omer count with exact count and snapshots."""
    start_date = dt.datetime(2024, 4, 24, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_YEARLY_EVENTS, start_date)

    # Exact count: 3 events (Holiday + Weekly portion + Omer count)
    assert len(events) == 3
    assert events == snapshot


@pytest.mark.freeze_time("2024-01-12 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_date_range_multiple_days(
    hass: HomeAssistant, get_calendar_events
) -> None:
    """Test getting events for multiple days with exact counts."""
    start_date = dt.datetime(2024, 1, 12, 0, 0, 0)
    end_date = dt.datetime(2024, 1, 14, 23, 59, 59)

    # Daily events: 3 days × 11 events per day = 33 events
    events = await get_calendar_events(
        hass, CALENDAR_DAILY_EVENTS, start_date, end_date
    )
    assert len(events) == 33


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_event_property_returns_next_event(hass: HomeAssistant) -> None:
    """Test that the event property returns the next upcoming event."""
    # Check daily events calendar
    state = hass.states.get(CALENDAR_DAILY_EVENTS)
    assert state is not None
    assert state.state == "on"
    assert "message" in state.attributes
    assert "start_time" in state.attributes


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.parametrize(
    "calendar_events",
    [
        {
            CONF_DAILY_EVENTS: [DailyCalendarEventType.DATE],
            CONF_LEARNING_SCHEDULE: [],
            CONF_YEARLY_EVENTS: [YearlyCalendarEventType.HOLIDAY],
        }
    ],
)
@pytest.mark.usefixtures("setup")
async def test_custom_configuration(hass: HomeAssistant, get_calendar_events) -> None:
    """Test calendar with custom event configuration and exact counts."""
    start_date = dt.datetime(2024, 1, 15, 0, 0, 0)

    # Test daily events - should only have DATE
    events = await get_calendar_events(hass, CALENDAR_DAILY_EVENTS, start_date)
    assert len(events) == 1  # Only DATE event

    # Test learning schedule - should be empty
    start_date_july = dt.datetime(2024, 7, 15, 0, 0, 0)
    events = await get_calendar_events(
        hass, CALENDAR_LEARNING_SCHEDULE, start_date_july
    )
    assert len(events) == 0  # No events configured

    # Test yearly events on holiday - should have the holiday
    start_date_purim = dt.datetime(2024, 3, 25, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_YEARLY_EVENTS, start_date_purim)
    assert len(events) == 1  # Shushan Purim


@pytest.mark.freeze_time("2024-09-07 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_weekly_portion(
    hass: HomeAssistant, get_calendar_events, snapshot: SnapshotAssertion
) -> None:
    """Test weekly portion event with snapshots."""
    start_date = dt.datetime(2024, 9, 7, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_YEARLY_EVENTS, start_date)

    # Check for weekly portion
    assert any("Parshat Hashavua" in event["description"] for event in events)
    assert events == snapshot


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_all_daily_event_types_present(
    hass: HomeAssistant, get_calendar_events
) -> None:
    """Test that all configured daily event types are present."""
    start_date = dt.datetime(2024, 1, 15, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_DAILY_EVENTS, start_date)

    # Extract event types from descriptions
    descriptions = {event["description"].split(":")[0] for event in events}

    # Should have all the expected event types
    expected_prefixes = {
        "Hebrew date",
        "Halachic dawn",
        "Halachic sunrise",
        "Latest time for Shema",  # codespell:ignore shema
        "Latest time for Tefilla",
        "Halachic midday",
        "Earliest time for Mincha",
        "Preferable time for Mincha",
        "Plag Hamincha",
        "Sunset",
        "Nightfall",
    }

    assert expected_prefixes.issubset(descriptions)


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_event_format_all_day_vs_timed(
    hass: HomeAssistant, get_calendar_events
) -> None:
    """Test that events have correct format for all-day vs timed events."""
    # Daily events - contains both all-day (DATE) and timed events
    start_date = dt.datetime(2024, 1, 15, 0, 0, 0)
    events = await get_calendar_events(hass, CALENDAR_DAILY_EVENTS, start_date)

    for event in events:
        if event["description"].startswith("Hebrew date"):
            # All-day event - should not have time component
            assert "T" not in event["start"]
            assert "T" not in event["end"]
        else:
            # Timed event - should have time component with timezone
            assert "T" in event["start"]
            assert "+" in event["start"] or "Z" in event["start"]
            # For instant events, start == end
            assert event["start"] == event["end"]
