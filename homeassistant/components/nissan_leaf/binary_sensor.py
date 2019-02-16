"""Plugged In Status Support for the Nissan Leaf."""
import logging

from homeassistant.components.nissan_leaf import (
    DATA_LEAF, DATA_PLUGGED_IN, LeafEntity)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of a Nissan Leaf binary sensor."""
    devices = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug(
            "binary_sensor setup_platform, vin=%s, datastore=%s", vin, datastore)
        devices.append(LeafPluggedInSensor(datastore))

    add_devices(devices, True)


class LeafPluggedInSensor(LeafEntity):
    """Plugged In Sensor class."""

    @property
    def name(self):
        """Sensor name."""
        return "{} {}".format(self.car.leaf.nickname, "Plug Status")

    @property
    def state(self):
        """Return true if plugged in."""
        return self.car.data[DATA_PLUGGED_IN]

    @property
    def icon(self):
        """Icon handling."""
        if self.car.data[DATA_PLUGGED_IN]:
            return 'mdi:power-plug'
        return 'mdi:power-plug-off'
