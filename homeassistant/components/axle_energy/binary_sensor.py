"""Binary sensor platform for Axle Energy."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import AxleConfigEntry, AxleCoordinator
from .entity import AxleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AxleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event activity sensor."""
    async_add_entities([AxleEventSensor(entry.runtime_data)])


class AxleEventSensor(AxleEntity, BinarySensorEntity):
    """Indicate whether the household's scheduled event is in progress."""

    _attr_translation_key = "event_in_progress"

    def __init__(self, coordinator: AxleCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_event_in_progress"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the current time is within the event."""
        if (event := self.coordinator.data) is None:
            return False
        return event.start <= dt_util.utcnow() < event.end
