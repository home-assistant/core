"""
Support for Melnor RainCloud sprinkler water timer.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.raincloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.raincloud import CONF_ATTRIBUTION
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, STATE_UNKNOWN, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['raincloud']

_LOGGER = logging.getLogger(__name__)

# Sensor types: label, desc, unit, icon
SENSOR_TYPES = {
    'battery': ['Battery', '%', ''],
    'next_cycle': ['Next Cycle', '', 'calendar-clock'],
    'rain_delay': ['Rain Delay', 'days', 'weather-rainy'],
    'watering_time': ['Remaining Watering Time', 'min', 'water-pump'],
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
        if sensor_type == 'battery':
            sensors.append(
                RainCloudSensor(raincloud.controller.faucet,
                                sensor_type))
        else:
            # create an sensor for each zone managed by a faucet
            for zone in raincloud.controller.faucet.zones:
                sensors.append(RainCloudSensor(zone, sensor_type))

    add_devices(sensors, True)
    return True


class RainCloudSensor(Entity):
    """A sensor implementation for raincloud device."""

    def __init__(self, data, sensor_type):
        """Initialize a sensor for raincloud device."""
        self._data = data
        self._sensor_type = sensor_type
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[2])
        self._name = "{0} {1}".format(
            self._data.name, SENSOR_TYPES.get(self._sensor_type)[0])
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug("Updating RainCloud sensor: %s", self._name)
        if self._sensor_type == 'battery':
            self._state = self._data.battery.strip('%')
        else:
            self._state = getattr(self._data, self._sensor_type)
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == 'battery' and self._state is not STATE_UNKNOWN:
            rounded_level = round(int(self._state), -1)
            if rounded_level < 10:
                self._icon = 'mdi:battery-outline'
            elif self._state == 100:
                self._icon = 'mdi:battery'
            else:
                self._icon = 'mdi:battery-{}'.format(str(rounded_level))
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[1]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['identifier'] = self._data.serial
        attrs['current_time'] = self._data.current_time
        return attrs
