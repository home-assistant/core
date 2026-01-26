"""Support for TheSilentWave sensors."""

import logging

from pysilentwave.exceptions import SilentWaveError

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TheSilentWaveConfigEntry, TheSilentWaveCoordinator
from .entity import TheSilentWaveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TheSilentWaveConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([TheSilentWaveBinarySensor(coordinator, entry.entry_id)])


class TheSilentWaveBinarySensor(TheSilentWaveEntity, BinarySensorEntity):
    """Representation of a TheSilentWave binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "status"
    _attr_name = None  # Set to None to use device name as this is the main sensor

    def __init__(self, coordinator: TheSilentWaveCoordinator, entry_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry_id)
        # Set a more specific unique_id for this sensor entity
        self._attr_unique_id = f"{entry_id}_status"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("status") == "on"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()

        # Subscribe to device events if available
        if hasattr(self.coordinator.client, "subscribe_to_events"):
            await self._subscribe_to_events()

    async def _subscribe_to_events(self) -> None:
        """Subscribe to device events for real-time updates."""
        try:
            unsubscribe_callback = await self.coordinator.client.subscribe_to_events(
                self.async_write_ha_state
            )
            self.async_on_remove(unsubscribe_callback)
        except SilentWaveError as err:
            _LOGGER.debug("Failed to subscribe to events: %s", err)
