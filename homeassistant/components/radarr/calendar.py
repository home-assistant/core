"""Support for Radarr calendar items."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RadarrEntity
from .const import DOMAIN
from .coordinator import CalendarUpdateCoordinator, RadarrEvent

CALENDAR_TYPE = EntityDescription(
    key="calendar",
    name=None,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Radarr calendar entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["calendar"]
    async_add_entities([RadarrCalendarEntity(coordinator, CALENDAR_TYPE)])


class RadarrCalendarEntity(RadarrEntity, CalendarEntity):
    """A Radarr calendar entity."""

    coordinator: CalendarUpdateCoordinator

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if not self.coordinator.event:
            return None
        return CalendarEvent(
            summary=self.coordinator.event.summary,
            start=self.coordinator.event.start,
            end=self.coordinator.event.end,
            description=self.coordinator.event.description,
        )

    # pylint: disable-next=hass-return-type
    async def async_get_events(  # type: ignore[override]
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[RadarrEvent]:
        """Get all events in a specific time frame."""
        return await self.coordinator.async_get_events(start_date, end_date)

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if self.coordinator.event:
            self._attr_extra_state_attributes = {
                "release_type": self.coordinator.event.release_type
            }
        else:
            self._attr_extra_state_attributes = {}
        super().async_write_ha_state()
