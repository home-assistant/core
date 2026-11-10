"""Support for iCloud Calendars."""

from datetime import datetime
from typing import override

from pyicloud.exceptions import PyiCloudException

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .account import IcloudConfigEntry
from .const import DOMAIN
from .coordinator import IcloudCalendarCoordinator, IcloudCalendarData, localize

# The coordinator owns the polling and the entities are read-only, so there is
# nothing here for Home Assistant to serialize.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IcloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the iCloud calendars."""
    coordinator = entry.runtime_data.calendar_coordinator
    assert coordinator is not None

    known: set[str] = set()

    @callback
    def _add_new_calendars() -> None:
        """Add entities for calendars that appeared since the last poll."""
        if not (new := set(coordinator.data or {}) - known):
            return
        known.update(new)
        async_add_entities(
            IcloudCalendarEntity(coordinator, entry, guid) for guid in new
        )

    _add_new_calendars()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_calendars))


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
            identifiers={(DOMAIN, f"{entry.unique_id}_account")},
            manufacturer="Apple",
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _calendar(self) -> IcloudCalendarData | None:
        """Return the cached calendar, or None once it is gone from iCloud."""
        return self.coordinator.data.get(self._guid)

    @property
    @override
    def available(self) -> bool:
        """Return True if the calendar still exists in iCloud."""
        return super().available and self._calendar is not None

    @property
    @override
    def name(self) -> str | None:
        """Return the name of the calendar."""
        if (calendar := self._calendar) is not None:
            return calendar.name
        return None

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the event in progress, or the next one to start."""
        if (calendar := self._calendar) is None:
            return None

        now = dt_util.now()
        upcoming: CalendarEvent | None = None
        for event in calendar.events:
            if localize(event.end) <= now:
                continue
            if localize(event.start) <= now:
                return event
            if upcoming is None or localize(event.start) < localize(upcoming.start):
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
