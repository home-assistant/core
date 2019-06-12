"""Plugged In Status Support for the Nissan Leaf."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DATA_CHARGING, DATA_LEAF, DATA_PLUGGED_IN, LeafEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up of a Nissan Leaf binary sensor."""
    if discovery_info is None:
        return

    devices = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding binary_sensors for vin=%s", vin)
        devices.append(LeafPluggedInSensor(datastore))
        devices.append(LeafChargingSensor(datastore))

    add_entities(devices, True)


class LeafPluggedInSensor(LeafEntity, BinarySensorDevice):
    """Plugged In Sensor class."""

    @property
    def name(self):
        """Sensor name."""
        return "{} {}".format(self.car.leaf.nickname, "Plug Status")

    @property
    def is_on(self):
        """Return true if plugged in."""
        return self.car.data[DATA_PLUGGED_IN]

    @property
    def icon(self):
        """Icon handling."""
        if self.car.data[DATA_PLUGGED_IN]:
            return 'mdi:power-plug'
        return 'mdi:power-plug-off'


class LeafChargingSensor(LeafEntity, BinarySensorDevice):
    """Charging Sensor class."""

    @property
    def name(self):
        """Sensor name."""
        return "{} {}".format(self.car.leaf.nickname, "Charging Status")

    @property
    def is_on(self):
        """Return true if charging."""
        return self.car.data[DATA_CHARGING]

    @property
    def icon(self):
        """Icon handling."""
        if self.car.data[DATA_CHARGING]:
            return 'mdi:flash'
        return 'mdi:flash-off'
