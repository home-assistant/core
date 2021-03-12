"""Support for Gardena Smart System websocket connection status."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)

from custom_components.gardena_smart_system import GARDENA_SYSTEM
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Gardena websocket connection status."""
    async_add_entities([SmartSystemWebsocketStatus(hass.data[DOMAIN][GARDENA_SYSTEM].smart_system)], True)


class SmartSystemWebsocketStatus(BinarySensorEntity):
    """Representation of Gardena Smart System websocket connection status."""

    def __init__(self, smart_system) -> None:
        """Initialize the binary sensor."""
        super().__init__()
        self._unique_id = "smart_gardena_websocket_status"
        self._name = "Gardena Smart System connection"
        self._smart_system = smart_system

    async def async_added_to_hass(self):
        """Subscribe to events."""
        self._smart_system.add_ws_status_callback(self.update_callback)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._smart_system.is_ws_connected

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False

    def update_callback(self, status):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY
