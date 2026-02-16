"""Tests for the Jewish Calendar calendar platform.

The calendar platform creates three calendar entities:
- Daily events: Hebrew date (all-day) and halachic times (timed instants)
- Yearly events: Holidays, weekly Torah portions, Omer count
- Learning schedule: Daf Yomi (disabled by default)

Tests verify platform behavior: entity registration, event formatting,
configuration filtering, and date-based logic (e.g., weekly portions
are restricted to Saturdays, with a Simchat Torah exception).
We are testing the calendar platform, not the results of py-libhdate.
"""

from collections.abc import Generator
import datetime as dt
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.jewish_calendar.const import (
    CONF_DAILY_EVENTS,
    CONF_LEARNING_SCHEDULE,
    CONF_YEARLY_EVENTS,
    DailyCalendarEventType,
    YearlyCalendarEventType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

# Entity IDs for the three calendars
DAILY_EVENTS = "calendar.jewish_calendar_daily_events"
LEARNING_SCHEDULE = "calendar.jewish_calendar_learning_schedule"
YEARLY_EVENTS = "calendar.jewish_calendar_yearly_events"


@pytest.fixture(autouse=True)
def calendar_only() -> Generator[None]:
    """Load only the calendar platform for focused testing."""
    with patch(
        "homeassistant.components.jewish_calendar.PLATFORMS",
        [Platform.CALENDAR],
    ):
        yield


# ─── Entity Registration ─────────────────────────────────────────────
# Verify the three calendar entities are created and registered properly,
# including that the learning schedule calendar is disabled by default.


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test all calendar entities are registered with correct properties."""
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_learning_schedule_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the learning schedule calendar is disabled by default."""
    entry = entity_registry.async_get(LEARNING_SCHEDULE)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


# ─── Event Format ─────────────────────────────────────────────────────
# Daily events contain two types: all-day (Hebrew date) and timed instants
# (halachic times). These tests verify the format is correct.


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_all_day_event_format(hass: HomeAssistant, get_calendar_events) -> None:
    """Test Hebrew date is an all-day event with date-only start/end."""
    events = await get_calendar_events(hass, DAILY_EVENTS, dt.datetime(2024, 1, 15))
    date_events = [e for e in events if e["description"].startswith("Hebrew date")]

    assert len(date_events) == 1
    assert "T" not in date_events[0]["start"]
    assert "T" not in date_events[0]["end"]


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_timed_event_format(hass: HomeAssistant, get_calendar_events) -> None:
    """Test halachic times are timed instants (start == end, with timezone)."""
    events = await get_calendar_events(hass, DAILY_EVENTS, dt.datetime(2024, 1, 15))
    timed_events = [e for e in events if not e["description"].startswith("Hebrew date")]

    assert len(timed_events) > 0
    for event in timed_events:
        assert "T" in event["start"], f"Expected datetime, got date-only: {event}"
        assert event["start"] == event["end"], (
            f"Timed events should be instants: {event}"
        )


# ─── Daily Events ────────────────────────────────────────────────────
# The daily events calendar produces the Hebrew date and configured
# halachic times for each day. Times differ by location and timezone.


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_daily_events(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test default daily events for a regular day."""
    events = await get_calendar_events(hass, DAILY_EVENTS, dt.datetime(2024, 1, 15))
    # Default config: 1 all-day date + 3 time-based events (by default)
    assert len(events) == 4
    assert events == snapshot


# ─── Yearly Events: Weekly Torah Portion ──────────────────────────────
# The weekly Torah portion (Parshat Hashavua) appears only on Saturdays
# (Shabbat). On Shabbat that coincides with a holiday where no regular
# portion is read, no portion event is created. The sole exception is
# Simchat Torah, which always shows V'Zot HaBracha regardless of the
# day of the week it falls on.


@pytest.mark.freeze_time("2024-01-13 12:00:00")
@pytest.mark.parametrize("location_data", ["New York", "Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_weekly_portion_on_shabbat(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test weekly Torah portion appears on a regular Saturday."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 1, 13))
    assert any("Parshat Hashavua" in e["description"] for e in events)
    assert events == snapshot


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.parametrize(
    "query_date",
    [
        pytest.param(dt.datetime(2024, 1, 12), id="friday"),
        pytest.param(dt.datetime(2024, 1, 15), id="monday"),
    ],
)
@pytest.mark.usefixtures("setup")
async def test_no_weekly_portion_on_weekday(
    hass: HomeAssistant, get_calendar_events, query_date: dt.datetime
) -> None:
    """Test weekly Torah portion does not appear on non-Saturday weekdays."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, query_date)
    assert not any("Parshat Hashavua" in e["description"] for e in events)


@pytest.mark.freeze_time("2024-04-27 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_no_weekly_portion_on_holiday_shabbat(
    hass: HomeAssistant, get_calendar_events
) -> None:
    """Test no weekly portion on Shabbat during Hol HaMoed Pesach."""
    # 2024-04-27 is Saturday during Hol HaMoed Pesach — no regular parasha is read
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 4, 27))
    assert not any("Parshat Hashavua" in e["description"] for e in events)


@pytest.mark.freeze_time("2024-10-24 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_weekly_portion_on_simchat_torah_israel(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Torah portion appears on Simchat Torah in Israel (Thursday)."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 10, 24))
    assert any("Parshat Hashavua" in e["description"] for e in events)
    assert events == snapshot


@pytest.mark.freeze_time("2024-10-25 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_weekly_portion_on_simchat_torah_diaspora(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Torah portion appears on Simchat Torah in diaspora (Friday)."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 10, 25))
    assert any("Parshat Hashavua" in e["description"] for e in events)
    assert events == snapshot


# ─── Yearly Events: Holidays ─────────────────────────────────────────
# Holidays appear on their respective dates as all-day events.


@pytest.mark.freeze_time("2024-03-25 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_holiday(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test holiday event appears on a holiday date (Shushan Purim)."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 3, 25))
    assert any("Jewish Holiday" in e["description"] for e in events)
    assert events == snapshot


# ─── Yearly Events: Omer Count ───────────────────────────────────────
# The Omer count appears daily during the 49-day counting period
# between Pesach and Shavuot.


@pytest.mark.freeze_time("2024-04-24 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.parametrize(
    "calendar_events", [{CONF_YEARLY_EVENTS: [YearlyCalendarEventType.OMER_COUNT]}]
)
@pytest.mark.usefixtures("setup")
async def test_omer_count(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Omer count event appears during the counting period."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 4, 24))
    assert any("Sefirat HaOmer" in e["description"] for e in events)
    assert events == snapshot


# ─── Yearly Events: Candle Lighting & Havdalah ───────────────────────
# These timed events are not in the default configuration but can be
# explicitly enabled. Candle lighting appears before Shabbat/holidays,
# Havdalah appears after.


@pytest.mark.freeze_time("2024-01-12 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_candle_lighting_on_friday(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test candle lighting appears on Friday when configured."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 1, 12))
    assert len(events) == 1
    assert "Candle lighting" in events[0]["description"]
    assert events == snapshot


@pytest.mark.freeze_time("2024-01-13 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.parametrize(
    "calendar_events",
    [
        {
            CONF_YEARLY_EVENTS: [
                YearlyCalendarEventType.CANDLE_LIGHTING,
                YearlyCalendarEventType.HAVDALAH,
            ],
        }
    ],
)
@pytest.mark.usefixtures("setup")
async def test_havdalah_on_saturday(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Havdalah appears on Saturday when configured."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 1, 13))
    assert len(events) == 1
    assert "Havdalah" in events[0]["description"]
    assert events == snapshot


# ─── Learning Schedule ───────────────────────────────────────────────
# The learning schedule calendar (Daf Yomi) is disabled by default.
# When enabled, it shows the daily Daf Yomi page.


@pytest.mark.freeze_time("2024-07-15 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup")
async def test_learning_schedule_events(
    hass: HomeAssistant,
    get_calendar_events,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Daf Yomi event appears when learning schedule is enabled."""
    events = await get_calendar_events(
        hass, LEARNING_SCHEDULE, dt.datetime(2024, 7, 15)
    )
    assert len(events) == 1
    assert events == snapshot


# ─── Custom Configuration ────────────────────────────────────────────
# Users can customize which event types are shown in each calendar.
# This verifies that the platform respects the configuration and only
# produces events for the types the user selected.


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.parametrize(
    "calendar_events",
    [{CONF_DAILY_EVENTS: [DailyCalendarEventType.DATE]}],
)
@pytest.mark.usefixtures("setup")
async def test_daily_events_custom_filter(
    hass: HomeAssistant, get_calendar_events
) -> None:
    """Test only configured daily event types are shown."""
    events = await get_calendar_events(hass, DAILY_EVENTS, dt.datetime(2024, 1, 15))
    assert len(events) == 1
    assert events[0]["description"].startswith("Hebrew date")


@pytest.mark.freeze_time("2024-03-25 12:00:00")
@pytest.mark.parametrize("location_data", ["Jerusalem"], indirect=True)
@pytest.mark.parametrize(
    "calendar_events",
    [{CONF_YEARLY_EVENTS: [YearlyCalendarEventType.HOLIDAY]}],
)
@pytest.mark.usefixtures("setup")
async def test_yearly_events_custom_filter(
    hass: HomeAssistant, get_calendar_events
) -> None:
    """Test only configured yearly event types are shown (holiday on Shushan Purim)."""
    events = await get_calendar_events(hass, YEARLY_EVENTS, dt.datetime(2024, 3, 25))
    assert all("Jewish Holiday" in e["description"] for e in events)
    assert not any("Parshat Hashavua" in e["description"] for e in events)


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.parametrize(
    "calendar_events",
    [
        {
            CONF_DAILY_EVENTS: [],
            CONF_YEARLY_EVENTS: [],
            CONF_LEARNING_SCHEDULE: [],
        }
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup")
async def test_empty_event_config(hass: HomeAssistant, get_calendar_events) -> None:
    """Test empty event configuration produces no events for any calendar."""
    start = dt.datetime(2024, 1, 15)
    assert await get_calendar_events(hass, DAILY_EVENTS, start) == []
    assert await get_calendar_events(hass, YEARLY_EVENTS, start) == []
    assert await get_calendar_events(hass, LEARNING_SCHEDULE, start) == []


# ─── Date Range Queries ──────────────────────────────────────────────
# The calendar supports querying events over multi-day ranges.
# Events are generated independently for each day in the range.


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_multi_day_range(hass: HomeAssistant, get_calendar_events) -> None:
    """Test events are returned for each day in a multi-day range."""
    start = dt.datetime(2024, 1, 15, 0, 0, 0)
    end = dt.datetime(2024, 1, 17, 23, 59, 59)
    events = await get_calendar_events(hass, DAILY_EVENTS, start, end)
    # 3 days × 4 default daily events per day = 12
    assert len(events) == 12


# ─── Calendar State / Event Property ─────────────────────────────────
# The CalendarEntity.event property returns the next upcoming event,
# which determines the entity state (on/off) and the state attributes.


@pytest.mark.freeze_time("2024-01-15 12:00:00")
@pytest.mark.parametrize("location_data", ["New York"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_event_property(hass: HomeAssistant) -> None:
    """Test the entity state reflects the next upcoming event."""
    state = hass.states.get(DAILY_EVENTS)
    assert state is not None
    assert state.state == "on"
    assert "message" in state.attributes
    assert "start_time" in state.attributes
