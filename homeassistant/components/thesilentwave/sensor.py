"""Support for TheSilentWave sensors."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from typing import Callable

from .entity import TheSilentWaveEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor from a config entry."""
    coordinator = hass.data["thesilentwave"][entry.entry_id]
    async_add_entities([TheSilentWaveSensor(coordinator, entry.entry_id)], True)


class TheSilentWaveSensor(TheSilentWaveEntity, SensorEntity):
    """Representation of a TheSilentWave sensor."""

    def __init__(self, coordinator, entry_id):
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_name = (
            None  # Set to None to use device name as this is the main sensor.
        )
        self._unsubscribe_callback = None
        # Set a more specific unique_id for this sensor entity.
        self._attr_unique_id = f"thesilentwave_{entry_id}_status"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:power" if self.state == "on" else "mdi:power-off"

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()
        # Subscribe to any events from the client if available.
        if hasattr(self.coordinator._client, "subscribe_to_events"):
            self._unsubscribe_callback = (
                await self.coordinator._client.subscribe_to_events(self._handle_event)
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from events when entity is removed."""
        # Clean up subscriptions.
        if self._unsubscribe_callback is not None:
            self._unsubscribe_callback()
            self._unsubscribe_callback = None
        await super().async_will_remove_from_hass()

    async def _handle_event(self, event) -> None:
        """Handle events from the device."""
        self.async_write_ha_state()
