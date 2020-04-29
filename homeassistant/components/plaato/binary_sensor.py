"""Support for Plaato Airlock sensors."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_TOKEN

from .const import CONF_DEVICE_NAME, CONF_USE_WEBHOOK, DOMAIN
from .entity import PlaatoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Plaato sensor."""


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up Plaato from a config entry."""

    if not config_entry.data.get(CONF_USE_WEBHOOK, False):
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        if coordinator.data is not None:
            async_add_devices(
                PlaatoBinarySensor(
                    config_entry.data[CONF_TOKEN],
                    sensor_type,
                    config_entry.data[CONF_DEVICE_NAME],
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
