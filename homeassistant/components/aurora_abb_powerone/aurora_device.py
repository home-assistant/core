"""Top level class for AuroraABBPowerOneSolarPV inverters and sensors."""
import logging

from aurorapy.client import AuroraSerialClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


class AuroraDevice(Entity):
    """Representation of an Aurora ABB PowerOne device."""

    def __init__(self, client: AuroraSerialClient, config_entry: ConfigEntry):
        """Initialise the basic device."""
        self.config_entry = config_entry
        self.type = "device"
        self.client = client
        self._available = True

    @property
    def unique_id(self) -> str:
        """Return the unique id for this device."""
        serial = self.config_entry.data.get(ATTR_SERIAL_NUMBER, "dummy sn")
        return f"{serial}_{self.type}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "config_entry_id": self.config_entry.entry_id,
            "identifiers": {
                (DOMAIN, self.config_entry.data.get(ATTR_SERIAL_NUMBER, "dummy sn"))
            },
            "manufacturer": MANUFACTURER,
            "model": self.config_entry.data.get(ATTR_MODEL, "Model unknown"),
            "name": self.config_entry.data.get(ATTR_DEVICE_NAME, DEFAULT_DEVICE_NAME),
            "sw_version": self.config_entry.data.get(ATTR_FIRMWARE, "0.0.0"),
        }
