"""Support for HomeMatic binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import STATE_UNKNOWN
from . import ATTR_DISCOVER_DEVICES, HMDevice

ATTR_LOW_BAT = "LOW_BAT"
ATTR_LOWBAT = "LOWBAT"

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["homematic"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HomeMatic binary sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMBatterySensor(conf)
        devices.append(new_device)

    add_entities(devices)


class HMBatterySensor(HMDevice, BinarySensorDevice):
    """Representation of an homematic low battery sensor."""

    @property
    def device_class(self):
        """Return battery as a device class."""
        return "battery"

    @property
    def is_on(self):
        """Return True if battery is low."""
        is_on = self._data.get(ATTR_LOW_BAT, False) or self._data.get(
            ATTR_LOWBAT, False
        )
        return is_on

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        # Add state to data struct
        if self._state:
            self._data.update({self._state: STATE_UNKNOWN})
