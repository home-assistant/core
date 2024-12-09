"""Support for Wallbox calendar items."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGER_CALENDAR,
    CHARGER_DATA_KEY,
    CHARGER_LAST_EVENT,
    CHARGER_SERIAL_NUMBER_KEY,
    DOMAIN,
)
from .coordinator import WallboxCoordinator, WallboxEvent
from .entity import WallboxEntity

CALENDAR_TYPE = CalendarEntityDescription(
    key=CHARGER_CALENDAR, translation_key="calendar"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wallbox calendar entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WallboxCalendarEntity(coordinator, CALENDAR_TYPE)])


class WallboxCalendarEntity(WallboxEntity, CalendarEntity):
    """A Wallbox calendar entity."""

    def __init__(
        self, coordinator: WallboxCoordinator, description: CalendarEntityDescription
    ) -> None:
        """Initialize a Wallbox calendar."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"
        self._event: WallboxEvent | None = None

    @property
    def event(self) -> WallboxEvent | None:
        """Return the last event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return [
            CalendarEvent(
                summary=session.summary,
                start=session.start,
                end=session.end,
                description=session.description,
                location=session.location,
            )
            for session in await self.coordinator.async_get_sessions(
                self.coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY],
                start_date,
                end_date,
            )
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._event = self.coordinator.data[CHARGER_LAST_EVENT]
        super()._handle_coordinator_update()

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        if event := self.event:
            self._attr_extra_state_attributes = {
                "charger_name": event.charger_name,
                "username": event.username,
                "session_id": event.session_id,
                "currency": event.currency,
                "serial_number": event.serial_number,
                "energy": event.energy,
                "time": event.time,
                "session_cost": event.session_cost,
            }
        else:
            self._attr_extra_state_attributes = {}
        super().async_write_ha_state()
