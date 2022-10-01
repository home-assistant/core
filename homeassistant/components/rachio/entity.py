"""Adapter to wrap the rachiopy api for home assistant."""

from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DEFAULT_NAME, DOMAIN
from .device import RachioIro


class RachioDevice(Entity):
    """Base class for rachio devices."""

    _attr_should_poll = False

    def __init__(self, controller: RachioIro) -> None:
        """Initialize a Rachio device."""
        super().__init__()
        self._controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._controller.serial_number,
                )
            },
            connections={
                (
                    device_registry.CONNECTION_NETWORK_MAC,
                    self._controller.mac_address,
                )
            },
            name=self._controller.name,
            model=self._controller.model,
            manufacturer=DEFAULT_NAME,
            configuration_url="https://app.rach.io",
        )
