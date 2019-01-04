"""
Plugged In Status Support for the Nissan Leaf.

Documentation pending.
Please refer to the main platform component for configuration details
"""

import logging

from homeassistant.components.nissan_leaf import (
    DATA_LEAF, DATA_PLUGGED_IN, LeafEntity)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Nissan Leaf binary_sensor setup."""
    _LOGGER.debug("binary_sensor setup_platform, discovery_info=%s",
                  discovery_info)

    devices = []
    for key, value in hass.data[DATA_LEAF].items():
        _LOGGER.debug("binary_sensor setup_platform, key=%s, value=%s",
                      key, value)
        devices.append(LeafPluggedInSensor(value))

    add_devices(devices, True)


class LeafPluggedInSensor(LeafEntity):
    """Plugged In Sensor class."""

    @property
    def name(self):
        """Sensor name."""
        return self.car.leaf.nickname + " Plug Status"

    def log_registration(self):
        """Log registration."""
        _LOGGER.debug(
            "Registered LeafPluggedInSensor component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def state(self):
        """Return true if plugged in."""
        return self.car.data[DATA_PLUGGED_IN]

    @property
    def icon(self):
        """Icon handling."""
        if self.car.data[DATA_PLUGGED_IN]:
            return 'mdi:power-plug'
        else:
            return 'mdi:power-plug-off'
