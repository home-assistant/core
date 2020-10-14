"""Support for Plaato Airlock sensors."""

import logging

from pyplaato.plaato import PlaatoKeg

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from .const import CONF_USE_WEBHOOK, COORDINATOR, DOMAIN
from .entity import PlaatoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Plaato sensor."""


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up Plaato from a config entry."""

    if not config_entry.data.get(CONF_USE_WEBHOOK, False):
        coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
        if coordinator.data is not None:
            async_add_devices(
                PlaatoBinarySensor(
                    hass.data[DOMAIN][config_entry.entry_id],
                    sensor_type,
                    coordinator,
                )
                for sensor_type in coordinator.data.binary_sensors.keys()
            )
        return True

    return False


class PlaatoBinarySensor(PlaatoEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self._coordinator is not None:
            return self._coordinator.data.binary_sensors.get(self._sensor_type)
        return False

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self._coordinator is None:
            return None
        if self._sensor_type is PlaatoKeg.Pins.LEAK_DETECTION:
            return DEVICE_CLASS_PROBLEM
        if self._sensor_type is PlaatoKeg.Pins.POURING:
            return DEVICE_CLASS_OPENING
