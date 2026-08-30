"""Support for iCloud Calendars."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any, override

from pyicloud.exceptions import PyiCloudException

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .account import IcloudConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

# How much of the calendar to keep cached for the entity's current/next event.
# `async_get_events` queries iCloud directly for anything outside this window.
LOOKBACK = timedelta(days=1)
LOOKAHEAD = timedelta(days=30)


@dataclass(slots=True)
class IcloudCalendarData:
    """A calendar and the events cached for it."""

    name: str
    events: list[CalendarEvent]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iCloud calendars."""
    coordinator = IcloudCalendarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    known: set[str] = set()

    @callback
    def _add_new_calendars() -> None:
        """Add entities for calendars that appeared since the last poll."""
        if not (new := set(coordinator.data) - known):
            return
        known.update(new)
        async_add_entities(
            IcloudCalendarEntity(coordinator, entry, guid) for guid in new
        )

    _add_new_calendars()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_calendars))


class IcloudCalendarCoordinator(DataUpdateCoordinator[dict[str, IcloudCalendarData]]):
    """Keep a rolling window of events cached for the current/next lookup."""

    def __init__(self, hass: HomeAssistant, entry: IcloudConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.account = entry.runtime_data

    def fetch_events(
        self, start: datetime, end: datetime, guids: list[str] | None = None
    ) -> dict[str, list[CalendarEvent]]:
        """Return events per calendar between two points. Runs in the executor."""
        if (api := self.account.api) is None:
            raise UpdateFailed("iCloud account is not authenticated")

        wanted = set(guids) if guids else None
        result: dict[str, list[CalendarEvent]] = {guid: [] for guid in (wanted or ())}

        for event in api.calendar.get_events(from_dt=start, to_dt=end, as_objs=True):
            guid = getattr(event, "pguid", None)
            if guid is None or (wanted is not None and guid not in wanted):
                continue
            if (parsed := _as_calendar_event(event)) is not None:
                result.setdefault(guid, []).append(parsed)

        for events in result.values():
            events.sort(key=lambda event: _localize(event.start))
        return result

    def _fetch(self) -> dict[str, IcloudCalendarData]:
        """Fetch the calendars and their events. Runs in the executor."""
        if (api := self.account.api) is None:
            raise UpdateFailed("iCloud account is not authenticated")

        names = {
            calendar.guid: calendar.title
            for calendar in api.calendar.get_calendars(as_objs=True)
        }
        now = dt_util.now()
        events = self.fetch_events(now - LOOKBACK, now + LOOKAHEAD, list(names))

        return {
            guid: IcloudCalendarData(name=name, events=events.get(guid, []))
            for guid, name in names.items()
        }

    @override
    async def _async_update_data(self) -> dict[str, IcloudCalendarData]:
        """Fetch calendars and their upcoming events."""
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except PyiCloudException as err:
            raise UpdateFailed(f"Error fetching calendars: {err}") from err


class IcloudCalendarEntity(
    CoordinatorEntity[IcloudCalendarCoordinator], CalendarEntity
):
    """A calendar from iCloud."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IcloudCalendarCoordinator,
        entry: IcloudConfigEntry,
        guid: str,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._guid = guid
        self._attr_unique_id = f"{entry.unique_id}_{guid}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_calendars")},
            manufacturer="Apple",
            model="Calendar",
            name="Calendar",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the calendar still exists in iCloud."""
        return super().available and self._guid in self.coordinator.data

    @property
    @override
    def name(self) -> str | None:
        """Return the name of the calendar."""
        if (calendar := self.coordinator.data.get(self._guid)) is not None:
            return calendar.name
        return None

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the event in progress, or the next one to start."""
        if (calendar := self.coordinator.data.get(self._guid)) is None:
            return None

        now = dt_util.now()
        upcoming: CalendarEvent | None = None
        for event in calendar.events:
            if _localize(event.end) <= now:
                continue
            if _localize(event.start) <= now:
                return event
            if upcoming is None or _localize(event.start) < _localize(upcoming.start):
                upcoming = event

        return upcoming

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events in an arbitrary range."""
        try:
            events = await hass.async_add_executor_job(
                self.coordinator.fetch_events, start_date, end_date, [self._guid]
            )
        except PyiCloudException as err:
            raise HomeAssistantError(f"Error fetching events: {err}") from err

        return events.get(self._guid, [])


def _localize(value: date | datetime) -> datetime:
    """Return a comparable, timezone-aware datetime for a date or datetime."""
    if isinstance(value, datetime):
        return dt_util.as_local(value)
    return dt_util.start_of_local_day(value)


def _parse_apple_date(value: Any) -> datetime | None:
    """Parse the date format iCloud returns for calendar events.

    ``EventObject`` is annotated as holding ``datetime``, but pyicloud hands
    back the wire format unchanged: ``[yyyymmdd, year, month, day, hour,
    minute, minutes_since_midnight]``. Both forms are accepted so this keeps
    working if that is ever changed upstream.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 6:
        try:
            _, year, month, day, hour, minute = value[:6]
            return datetime(int(year), int(month), int(day), int(hour), int(minute))
        except TypeError, ValueError:
            _LOGGER.debug("Unparseable calendar date: %r", value)
    return None


def _as_calendar_event(event: Any) -> CalendarEvent | None:
    """Convert a pyicloud event into a Home Assistant calendar event."""
    start = _parse_apple_date(
        getattr(event, "local_start_date", None)
    ) or _parse_apple_date(getattr(event, "start_date", None))
    if start is None:
        return None

    end = _parse_apple_date(
        getattr(event, "local_end_date", None)
    ) or _parse_apple_date(getattr(event, "end_date", None))
    if end is None:
        end = start + timedelta(hours=1)

    start_value: date | datetime
    end_value: date | datetime
    if getattr(event, "all_day", False):
        start_value = start.date()
        end_value = end.date()
        # Home Assistant treats the end of an all-day event as exclusive.
        if end_value <= start_value:
            end_value = start_value + timedelta(days=1)
    else:
        start_value = dt_util.as_local(start)
        end_value = dt_util.as_local(end)
        if end_value <= start_value:
            end_value = start_value + timedelta(minutes=30)

    return CalendarEvent(
        uid=getattr(event, "guid", None) or None,
        summary=getattr(event, "title", None) or "",
        start=start_value,
        end=end_value,
        location=getattr(event, "location", None) or None,
    )
