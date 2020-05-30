"""Top level class for AuroraABBPowerOneSolarPV inverters and sensors."""
import logging

from aurorapy.client import AuroraSerialClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

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
        self._id = config_entry.entry_id
        self.type = "device"
        self.serialnum = config_entry.data.get(ATTR_SERIAL_NUMBER, "dummy sn")
        self._sw_version = config_entry.data.get(ATTR_FIRMWARE, "0.0.0")
        self._model = config_entry.data.get(ATTR_MODEL, "Model unknown")
        self.client = client
        self.device_name = config_entry.data.get(ATTR_DEVICE_NAME, DEFAULT_DEVICE_NAME)

    @property
    def unique_id(self) -> str:
        """Return the unique id for this device."""
        return slugify(f"{self.serialnum}_{self.type}")

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "config_entry_id": self._id,
            "identifiers": {(DOMAIN, self.serialnum)},
            "manufacturer": MANUFACTURER,
            "model": self._model,
            "name": self.device_name,
            "sw_version": self._sw_version,
        }
