"""Provides the Lupusec entity for Home Assistant."""
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, TYPE_TRANSLATION


class LupusecDevice(Entity):
    """Representation of a Lupusec device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, data, device, entry_id) -> None:
        """Initialize a sensor for Lupusec device."""
        self._data = data
        self._device = device
        self._entry_id = entry_id
        self._attr_unique_id = self.get_unique_id(
            device.device_id if device.device_id != "0" else entry_id
        )

    def update(self):
        """Update automation state."""
        self._device.refresh()

    def get_unique_id(self, device_id: str) -> str:
        """Create a unique_id id for a lupusec entity."""
        return f"{DOMAIN}_{device_id}"


class LupusecBaseSensor(LupusecDevice):
    """Lupusec Sensor base entity."""

    @property
    def device_info(self):
        """Return device information about the sensor."""
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": "Lupus Electronics",
            "serial_number": self._device.device_id,
            "model": self.get_type_name(),
            "via_device": (DOMAIN, self._entry_id),
        }

    def get_type_name(self):
        """Return the type of the sensor."""
        return TYPE_TRANSLATION.get(self._device.type, self._device.type)
