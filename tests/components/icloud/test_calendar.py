"""Tests for the iCloud calendar platform."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyicloud.exceptions import PyiCloudException
from pyicloud.services.calendar import CalendarObject, EventObject
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.icloud.coordinator import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import (
    AsyncMock,
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)

ENTITY_ID = "calendar.test_icloud_account_personal"


def _apple_date(value: datetime) -> list[int]:
    """Return a datetime in the wire format pyicloud passes through."""
    return [
        int(value.strftime("%Y%m%d")),
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.hour * 60 + value.minute,
    ]


def _event(
    guid: str,
    title: str,
    start: datetime,
    end: datetime,
    *,
    pguid: str = "cal1",
    all_day: bool = False,
    location: str = "",
    tz: str = "Floating",
) -> MagicMock:
    """Build a mock pyicloud event."""
    event = MagicMock(spec=EventObject)
    event.guid = guid
    event.pguid = pguid
    event.title = title
    event.all_day = all_day
    event.location = location
    event.tz = tz
    event.local_start_date = _apple_date(start)
    event.local_end_date = _apple_date(end)
    event.start_date = event.local_start_date
    event.end_date = event.local_end_date
    return event


def _calendar(guid: str, title: str) -> MagicMock:
    """Build a mock pyicloud calendar."""
    calendar = MagicMock(spec=CalendarObject)
    calendar.guid = guid
    calendar.title = title
    return calendar


@pytest.fixture(name="calendars")
def mock_calendars(icloud_client: AsyncMock) -> MagicMock:
    """Mock the calendar service with one calendar and one event."""
    service = icloud_client.api.calendar
    service.get_calendars.return_value = [_calendar("cal1", "Personal")]
    service.get_events.return_value = [
        _event(
            "ev1",
            "Dentist",
            datetime(2024, 5, 1, 10, 0),
            datetime(2024, 5, 1, 11, 0),
        )
    ]
    return service


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the config entry with only the calendar platform loaded."""
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.icloud.PLATFORMS", [Platform.CALENDAR]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a calendar becomes an entity."""
    await _setup(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_event_in_progress_wins(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a running event is preferred over a later one."""
    now = dt_util.now()
    calendars.get_events.return_value = [
        _event(
            "ev1",
            "Now",
            now.replace(tzinfo=None) - SCAN_INTERVAL,
            now.replace(tzinfo=None) + SCAN_INTERVAL,
        ),
        _event(
            "ev2",
            "Later",
            now.replace(tzinfo=None) + SCAN_INTERVAL * 2,
            now.replace(tzinfo=None) + SCAN_INTERVAL * 3,
        ),
    ]

    await _setup(hass, config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["message"] == "Now"


async def test_all_day_event_end_is_exclusive(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a single all-day event ends on the following day.

    iCloud reports the same day for start and end, but Home Assistant treats
    the end of an all-day event as exclusive.
    """
    calendars.get_events.return_value = [
        _event(
            "ev1",
            "Holiday",
            datetime(2024, 5, 1),
            datetime(2024, 5, 1),
            all_day=True,
        )
    ]

    await _setup(hass, config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "start_date_time": datetime(2024, 4, 30),
            "end_date_time": datetime(2024, 5, 3),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot


async def test_get_events_filters_to_the_requested_window(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that events outside the requested range are dropped.

    pyicloud sends both bounds as plain dates, so iCloud answers a one-hour
    request with everything on the boundary days.
    """
    calendars.get_events.return_value = [
        _event(
            "ev1",
            "Before",
            datetime(2024, 5, 1, 8, 0),
            datetime(2024, 5, 1, 9, 0),
        ),
        _event(
            "ev2",
            "Overlapping the start",
            datetime(2024, 5, 1, 9, 30),
            datetime(2024, 5, 1, 10, 30),
        ),
        _event(
            "ev3",
            "Spanning the window",
            datetime(2024, 5, 1, 7, 0),
            datetime(2024, 5, 1, 20, 0),
        ),
        _event(
            "ev4",
            "After",
            datetime(2024, 5, 1, 14, 0),
            datetime(2024, 5, 1, 15, 0),
        ),
    ]

    await _setup(hass, config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "start_date_time": datetime(2024, 5, 1, 10, 0),
            "end_date_time": datetime(2024, 5, 1, 11, 0),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot


async def test_new_calendar_added_on_later_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a calendar created after setup appears on a later refresh."""
    await _setup(hass, config_entry)
    assert hass.states.get("calendar.test_icloud_account_work") is None

    calendars.get_calendars.return_value = [
        _calendar("cal1", "Personal"),
        _calendar("cal2", "Work"),
    ]
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    # The scheduled refresh runs as a background task of the config entry.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("calendar.test_icloud_account_work") is not None


async def test_get_events_error_raises(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
) -> None:
    """Test that an iCloud error surfaces as a Home Assistant error."""
    await _setup(hass, config_entry)
    calendars.get_events.side_effect = PyiCloudException("boom")

    with pytest.raises(HomeAssistantError, match="Error fetching events"):
        await hass.services.async_call(
            CALENDAR_DOMAIN,
            "get_events",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "start_date_time": datetime(2024, 4, 30),
                "end_date_time": datetime(2024, 5, 3),
            },
            blocking=True,
            return_response=True,
        )


async def test_event_uses_its_own_timezone(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that an event in another timezone keeps its own instant.

    iCloud reports naive wall-clock times alongside a `tz` field, so assuming
    Home Assistant's timezone would place the event at the wrong instant.
    """
    calendars.get_events.return_value = [
        _event(
            "ev1",
            "Meeting",
            datetime(2024, 5, 1, 10, 0),
            datetime(2024, 5, 1, 11, 0),
            tz="Europe/Rome",
        )
    ]

    await _setup(hass, config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "start_date_time": datetime(2024, 4, 30),
            "end_date_time": datetime(2024, 5, 3),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot


async def test_datetime_dates_are_accepted(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that real datetimes are accepted alongside the wire format.

    pyicloud annotates `EventObject` as holding `datetime` but passes Apple's
    wire format through unchanged, so both forms are handled. A naive datetime
    is a wall-clock time in the event's own timezone, while an aware one
    already names its instant and must keep it.
    """
    naive = _event(
        "ev1",
        "Naive",
        datetime(2024, 5, 1, 10, 0),
        datetime(2024, 5, 1, 11, 0),
        tz="Europe/Rome",
    )
    naive.local_start_date = datetime(2024, 5, 1, 10, 0)
    naive.local_end_date = datetime(2024, 5, 1, 11, 0)

    aware = _event(
        "ev2",
        "Aware",
        datetime(2024, 5, 1, 10, 0),
        datetime(2024, 5, 1, 11, 0),
        tz="Europe/Rome",
    )
    aware.local_start_date = datetime(2024, 5, 1, 10, 0, tzinfo=dt_util.UTC)
    aware.local_end_date = datetime(2024, 5, 1, 11, 0, tzinfo=dt_util.UTC)

    calendars.get_events.return_value = [naive, aware]

    await _setup(hass, config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "start_date_time": datetime(2024, 4, 30),
            "end_date_time": datetime(2024, 5, 3),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot


async def test_unknown_event_timezone_falls_back(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    calendars: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a malformed timezone falls back to Home Assistant's own.

    The event has to survive the fetch rather than be dropped, and its
    wall-clock time is read in the default timezone.
    """
    calendars.get_events.return_value = [
        _event(
            "ev1",
            "Meeting",
            datetime(2024, 5, 1, 10, 0),
            datetime(2024, 5, 1, 11, 0),
            tz="Not/AZone",
        )
    ]

    await _setup(hass, config_entry)

    events = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "start_date_time": datetime(2024, 4, 30),
            "end_date_time": datetime(2024, 5, 3),
        },
        blocking=True,
        return_response=True,
    )
    assert events == snapshot
