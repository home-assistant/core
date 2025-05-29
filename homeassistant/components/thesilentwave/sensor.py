"""Support for TheSilentWave sensors."""

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TheSilentWaveCoordinator
from .entity import TheSilentWaveEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([TheSilentWaveBinarySensor(coordinator, entry.entry_id)], True)


class TheSilentWaveBinarySensor(TheSilentWaveEntity, BinarySensorEntity):
    """Representation of a TheSilentWave binary sensor."""

    _attr_translation_key = "status"

    def __init__(self, coordinator: TheSilentWaveCoordinator, entry_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_name = None  # Set to None to use device name as this is the main sensor
        self._unsubscribe_callback = None
        # Set a more specific unique_id for this sensor entity
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_status"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data is None:
            return None
        # Convert the coordinator data to a boolean state
        return self.coordinator.data == "on"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()
        # Only subscribe to events if we have a connection to the device
        if self.coordinator.has_connection and hasattr(
            self.coordinator.client, "subscribe_to_events"
        ):
            self._unsubscribe_callback = (
                await self.coordinator.client.subscribe_to_events(
                    self.async_write_ha_state
                )
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from events when entity is removed."""
        # Clean up subscriptions.
        if self._unsubscribe_callback is not None:
            self._unsubscribe_callback()
            self._unsubscribe_callback = None
        await super().async_will_remove_from_hass()
