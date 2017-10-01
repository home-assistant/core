"""
Support for Melnor RainCloud sprinkler water timer.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.raincloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.raincloud import (
    BINARY_SENSORS, DATA_RAINCLOUD, ICON_MAP, RainCloudEntity)
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_MONITORED_CONDITIONS

DEPENDENCIES = ['raincloud']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a raincloud device."""
    raincloud = hass.data[DATA_RAINCLOUD].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == 'status':
            sensors.append(
                RainCloudBinarySensor(raincloud.controller, sensor_type))
            sensors.append(
                RainCloudBinarySensor(raincloud.controller.faucet,
                                      sensor_type))

        else:
            # create an sensor for each zone managed by faucet
            for zone in raincloud.controller.faucet.zones:
                sensors.append(RainCloudBinarySensor(zone, sensor_type))

    add_devices(sensors, True)
    return True


class RainCloudBinarySensor(RainCloudEntity, BinarySensorDevice):
    """A sensor implementation for raincloud device."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating RainCloud sensor: %s", self._name)
        self._state = getattr(self.data, self._sensor_type)

    @property
    def icon(self):
        """Return the icon of this device."""
        if self._sensor_type == 'is_watering':
            return 'mdi:water' if self.is_on else 'mdi:water-off'
        elif self._sensor_type == 'status':
            return 'mdi:pipe' if self.is_on else 'mdi:pipe-disconnected'
        return ICON_MAP.get(self._sensor_type)
