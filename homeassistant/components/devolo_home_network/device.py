"""Generic platform."""
from devolo_plc_api.device import Device

from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class DevoloDevice(Entity):
    """Representation of a devolo home network device."""

    def __init__(self, device: Device, device_name: str):
        """Initialize a devolo home network device."""
        self._enabled_default: bool
        self._icon: str
        self._name: str
        self._unique_id: str

        self._device = device
        self._state = 0
        self._device_name = device_name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.serial_number)},
            "manufacturer": "devolo",
            "model": self._device.product,
            "name": self._device_name,
            "sw_version": self._device.firmware_version,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def icon(self) -> str:
        """Return icon."""
        return self._icon

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the device."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return self._unique_id

    # TODO evaluate entity_picture
