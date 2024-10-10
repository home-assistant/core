"""Support for Wallbox calendar items."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGER_DATA_KEY,
    CHARGER_LAST_EVENT,
    CHARGER_SERIAL_NUMBER_KEY,
    DOMAIN,
)
from .coordinator import WallboxCoordinator, WallboxEvent
from .entity import WallboxEntity

CALENDAR_TYPE = EntityDescription(
    key="calendar",
    name=None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Radarr calendar entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WallboxCalendarEntity(coordinator, CALENDAR_TYPE)])


class WallboxCalendarEntity(WallboxEntity, CalendarEntity):
    """A Wallbox calendar entity."""

    def __init__(
        self, coordinator: WallboxCoordinator, description: EntityDescription
    ) -> None:
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the last event."""
        if not self.coordinator.data[CHARGER_LAST_EVENT]:
            return None
        return CalendarEvent(
            summary=self.coordinator.data[CHARGER_LAST_EVENT].summary,
            start=self.coordinator.data[CHARGER_LAST_EVENT].start,
            end=self.coordinator.data[CHARGER_LAST_EVENT].end,
            description=self.coordinator.data[CHARGER_LAST_EVENT].description,
        )

    # pylint: disable-next=hass-return-type
    async def async_get_events(  # type: ignore[override]
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[WallboxEvent]:
        """Get all events in a specific time frame."""
        return await self.coordinator.async_get_sessions(
            self.coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY],
            start_date,
            end_date,
        )

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if self.coordinator.data[CHARGER_LAST_EVENT]:
            self._attr_extra_state_attributes = {
                "charger_name": self.coordinator.data[CHARGER_LAST_EVENT].charger_name,
                "username": self.coordinator.data[CHARGER_LAST_EVENT].username,
                "session_id": self.coordinator.data[CHARGER_LAST_EVENT].session_id,
                "currency": self.coordinator.data[CHARGER_LAST_EVENT].currency,
                "session_type": self.coordinator.data[CHARGER_LAST_EVENT].session_type,
                "serial_number": self.coordinator.data[
                    CHARGER_LAST_EVENT
                ].serial_number,
                "energy": self.coordinator.data[CHARGER_LAST_EVENT].energy,
                "mid_energy": self.coordinator.data[CHARGER_LAST_EVENT].mid_energy,
                "cost_kw": self.coordinator.data[CHARGER_LAST_EVENT].cost_kw,
                "session_cost": self.coordinator.data[CHARGER_LAST_EVENT].session_cost,
            }
        else:
            self._attr_extra_state_attributes = {}
        super().async_write_ha_state()
