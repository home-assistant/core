"""
Support for Melnor RainCloud sprinkler water timer.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.raincloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.raincloud import (
    CONF_ATTRIBUTION, DATA_RAINCLOUD, RainCloudHub)
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION)

DEPENDENCIES = ['raincloud']

_LOGGER = logging.getLogger(__name__)

# Sensor types: label, desc, unit, icon
SENSOR_TYPES = {
    'auto_watering': ['Automatic Watering', 'mdi:autorenew'],
    'manual_watering': ['Manual Watering', 'water-pump'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a raincloud device."""
    raincloud_hub = hass.data[DATA_RAINCLOUD]
    raincloud = raincloud_hub.data
    default_watering_timer = raincloud_hub.default_watering_timer

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        # create an sensor for each zone managed by faucet
        for zone in raincloud.controller.faucet.zones:
            sensors.append(
                RainCloudSwitch(hass,
                                zone,
                                sensor_type,
                                default_watering_timer))

    add_devices(sensors, True)
    return True


class RainCloudSwitch(RainCloudHub, SwitchDevice):
    """A switch implementation for raincloud device."""

    def __init__(self, hass, data, sensor_type, default_watering_timer):
        """Initialize a switch for raincloud device."""
        self._hass = hass
        self._sensor_type = sensor_type
        self.data = data
        self._default_watering_timer = default_watering_timer
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[1])
        self._name = "{0} {1}".format(
            self.data.name, SENSOR_TYPES.get(self._sensor_type)[0])
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self):
        """Turn the device on."""
        if self._sensor_type == 'manual_watering':
            self.data.watering_time = self._default_watering_timer
        elif self._sensor_type == 'auto_watering':
            self.data.auto_watering = True
        self._state = True

    def turn_off(self):
        """Turn the device off."""
        if self._sensor_type == 'manual_watering':
            self.data.watering_time = 'off'
        elif self._sensor_type == 'auto_watering':
            self.data.auto_watering = False
        self._state = False

    def update(self):
        """Update device state."""
        _LOGGER.debug("Updating RainCloud switch: %s", self._name)
        if self._sensor_type == 'manual_watering':
            self._state = bool(self.data.watering_time)
        elif self._sensor_type == 'auto_watering':
            self._state = self.data.auto_watering

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'current_time': self.data.current_time,
            'default_manual_timer': self._default_watering_timer,
            'identifier': self.data.serial
        }
