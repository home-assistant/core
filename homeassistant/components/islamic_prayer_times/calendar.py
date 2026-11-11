"""Read-only calendar of calculated prayer windows."""

from datetime import datetime, timedelta
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAME
from .coordinator import (
    IslamicPrayerDataUpdateCoordinator,
    IslamicPrayerTimesConfigEntry,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IslamicPrayerTimesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a prayer calendar for this location."""
    async_add_entities([IslamicPrayerCalendar(config_entry.runtime_data)])


class IslamicPrayerCalendar(
    CoordinatorEntity[IslamicPrayerDataUpdateCoordinator], CalendarEntity
):
    """Prayer windows calculated for a location."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: IslamicPrayerDataUpdateCoordinator) -> None:
        """Initialize the prayer calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-prayers"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the current prayer windows could be calculated."""
        return super().available and self.coordinator.prayer_windows is not None

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next prayer window."""
        now = dt_util.utcnow()
        return next(
            (
                CalendarEvent(
                    start=window.start,
                    end=window.end,
                    summary=window.name,
                    description=window.description,
                )
                for window in self.coordinator.prayer_windows or ()
                if window.end > now
            ),
            None,
        )

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return prayer windows overlapping a requested time range."""
        start = dt_util.as_utc(start_date)
        end = dt_util.as_utc(end_date)
        # UTC-adjacent dates cover windows crossing midnight at any longitude.
        day = start.date() - timedelta(days=1)
        last_day = end.date() + timedelta(days=1)
        events: list[CalendarEvent] = []
        while day <= last_day:
            events.extend(
                CalendarEvent(
                    start=window.start,
                    end=window.end,
                    summary=window.name,
                    description=window.description,
                )
                for window in self.coordinator.get_prayer_windows(day)
                if window.end > start and window.start < end
            )
            day += timedelta(days=1)
        return sorted(events, key=lambda event: event.start)
