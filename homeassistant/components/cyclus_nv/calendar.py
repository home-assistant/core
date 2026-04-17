"""Support for Cyclus NV Calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_BAG_ID, WASTE_TYPE_TO_DESCRIPTION
from .coordinator import CyclusNVConfigEntry
from .entity import CyclusNVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CyclusNVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cyclus NV calendar based on a config entry."""
    async_add_entities([CyclusNVCalendar(entry)])


class CyclusNVCalendar(CyclusNVEntity, CalendarEntity):
    """Defines a Cyclus NV calendar."""

    _attr_name = None
    _attr_translation_key = "calendar"

    def __init__(self, entry: CyclusNVConfigEntry) -> None:
        """Initialize the Cyclus NV calendar entity."""
        super().__init__(entry)
        self._attr_unique_id = entry.data[CONF_BAG_ID]
        self._event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            CalendarEvent(
                summary=WASTE_TYPE_TO_DESCRIPTION[e.waste_type],
                start=e.pickup_date,
                end=e.pickup_date + timedelta(days=1),
            )
            for e in self.coordinator.data
            if start_date.date() <= e.pickup_date <= end_date.date()
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        today = dt_util.now().date()
        self._event = None
        for event in sorted(self.coordinator.data, key=lambda e: e.pickup_date):
            if event.pickup_date >= today:
                self._event = CalendarEvent(
                    summary=WASTE_TYPE_TO_DESCRIPTION[event.waste_type],
                    start=event.pickup_date,
                    end=event.pickup_date + timedelta(days=1),
                )
                break
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
