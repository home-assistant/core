"""
Support for Hydrawise sprinkler.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hydrawise/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.hydrawise import (
    DATA_HYDRAWISE, HydrawiseEntity, DEVICE_MAP, DEVICE_MAP_INDEX, SENSORS)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS

DEPENDENCIES = ['hydrawise']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSORS):
        vol.All(cv.ensure_list, [vol.In(SENSORS)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for zone in hydrawise.relays:
            sensors.append(HydrawiseSensor(zone, sensor_type))

    add_entities(sensors, True)


class HydrawiseSensor(HydrawiseEntity):
    """A sensor implementation for Hydrawise device."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        mydata = self.hass.data[DATA_HYDRAWISE].data
        _LOGGER.debug("Updating Hydrawise sensor: %s", self._name)
        if self._sensor_type == 'watering_time':
            if not mydata.running:
                self._state = 0
            else:
                if int(mydata.running[0]['relay']) == self.data['relay']:
                    self._state = int(mydata.running[0]['time_left']/60)
                else:
                    self._state = 0
        else:  # _sensor_type == 'next_cycle'
            for relay in mydata.relays:
                if relay['relay'] == self.data['relay']:
                    if relay['nicetime'] == 'Not scheduled':
                        self._state = 'not_scheduled'
                    else:
                        self._state = relay['nicetime'].split(',')[0] + \
                            ' ' + relay['nicetime'].split(' ')[3]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return DEVICE_MAP[self._sensor_type][
            DEVICE_MAP_INDEX.index('ICON_INDEX')]
