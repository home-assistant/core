"""Adapter to wrap the rachiopy api for home assistant."""

from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_NAME, DOMAIN


class RachioDevice(Entity):
    """Base class for rachio devices."""

    def __init__(self, controller):
        """Initialize a Rachio device."""
        super().__init__()
        self._controller = controller

    @property
    def should_poll(self) -> bool:
        """Declare that this entity pushes its state to HA."""
        return False

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._controller.serial_number,)},
            "connections": {
                (device_registry.CONNECTION_NETWORK_MAC, self._controller.mac_address,)
            },
            "name": self._controller.name,
            "model": self._controller.model,
            "manufacturer": DEFAULT_NAME,
        }
