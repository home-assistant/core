"""
Support for Melnor RainCloud sprinkler water timer.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.raincloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.raincloud import CONF_ATTRIBUTION
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION)

DEPENDENCIES = ['raincloud']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'is_watering': ['Watering', ''],
    'status': ['Status', ''],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a raincloud device."""
    raincloud = hass.data.get('raincloud').data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == 'status':
            sensors.append(
                RainCloudBinarySensor(hass,
                                      raincloud.controller,
                                      sensor_type))
            sensors.append(
                RainCloudBinarySensor(hass,
                                      raincloud.controller.faucet,
                                      sensor_type))

        else:
            # create an sensor for each zone managed by faucet
            for zone in raincloud.controller.faucet.zones:
                sensors.append(RainCloudBinarySensor(hass, zone, sensor_type))

    add_devices(sensors, True)
    return True


class RainCloudBinarySensor(BinarySensorDevice):
    """A sensor implementation for raincloud device."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for raincloud device."""
        super().__init__()
        self._sensor_type = sensor_type
        self._data = data
        self._name = "{0} {1}".format(
            self._data.name, SENSOR_TYPES.get(self._sensor_type)[0])
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating RainCloud sensor: %s", self._name)
        self._state = getattr(self._data, self._sensor_type)

    @property
    def icon(self):
        """Return the icon of this device."""
        if self._sensor_type == 'is_watering':
            return 'mdi:water' if self.is_on else 'mdi:water-off'
        elif self._sensor_type == 'status':
            return 'mdi:pipe' if self.is_on else 'mdi:pipe-disconnected'
        return SENSOR_TYPES.get(self._sensor_type)[1]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['current_time'] = self._data.current_time
        attrs['identifier'] = self._data.serial
        return attrs
