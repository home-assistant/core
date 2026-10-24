"""Calendar platform for the Open Home Foundation Events integration."""

from datetime import datetime
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance

from .const import DOMAIN
from .coordinator import OHFEventsConfigEntry, OHFEventsCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OHFEventsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a calendar for every area."""
    coordinator = entry.runtime_data
    for subentry in entry.subentries.values():
        async_add_entities(
            [OHFEventsCalendar(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OHFEventsCalendar(CoordinatorEntity[OHFEventsCoordinator], CalendarEntity):
    """Calendar with all events within an area."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: OHFEventsCoordinator, subentry: ConfigSubentry
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._latitude: float = subentry.data[CONF_LATITUDE]
        self._longitude: float = subentry.data[CONF_LONGITUDE]
        self._radius: float = subentry.data[CONF_RADIUS]
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Open Home Foundation",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _events_in_area(self) -> list[CalendarEvent]:
        """Return all events whose venue lies within the area."""
        return [
            item.event
            for item in self.coordinator.data
            if (
                (
                    meters := distance(
                        self._latitude,
                        self._longitude,
                        item.latitude,
                        item.longitude,
                    )
                )
                is not None
                and meters <= self._radius
            )
        ]

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        now = dt_util.now()
        upcoming = [
            event for event in self._events_in_area() if event.end_datetime_local > now
        ]
        return min(upcoming, key=lambda event: event.start_datetime_local, default=None)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events within a time frame."""
        return [
            event
            for event in self._events_in_area()
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]
