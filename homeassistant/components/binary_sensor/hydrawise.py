"""
Support for Hydrawise sprinkler.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.hydrawise/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.hydrawise import (
    BINARY_SENSORS, DATA_HYDRAWISE, HydrawiseEntity, ICON_MAP)
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_MONITORED_CONDITIONS

DEPENDENCIES = ['hydrawise']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a hydrawise device."""
    hydrawise = hass.data[DATA_HYDRAWISE].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type in ['status', 'rain_sensor']:
            sensors.append(
                HydrawiseBinarySensor(
                    hydrawise.controller_status, sensor_type))

        else:
            # create a sensor for each zone
            for zone in hydrawise.relays:
                zone_data = zone
                zone_data['running'] = \
                    hydrawise.controller_status.get('running', False)
                sensors.append(HydrawiseBinarySensor(zone_data, sensor_type))

    add_devices(sensors, True)
    return True


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorDevice):
    """A sensor implementation for hydrawise device."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Updating Hydrawise binary sensor: %s", self._name)
        mydata = self.hass.data['hydrawise'].data
        if self._sensor_type == 'status':
            self._state = mydata.status == 'All good!'
        elif self._sensor_type == 'rain_sensor':
            for sensor in mydata.sensors:
                if sensor['name'] == 'Rain':
                    if sensor['active'] == 1:
                        self._state = True
                    else:
                        self._state = False
                    break
        elif self._sensor_type == 'is_watering':
            if mydata.running is None or not mydata.running:
                self._state = False
            else:
                if int(mydata.running[0]['relay']) == self.data.get('relay'):
                    self._state = True
                else:
                    self._state = False

    @property
    def icon(self):
        """Return the icon of this device."""
        if self._sensor_type == 'is_watering':
            return 'mdi:water' if self.is_on else 'mdi:water-off'
        elif self._sensor_type == 'status':
            return (
                'mdi:cloud-outline' if self.is_on else 'mdi:cloud-off-outline')
        elif self._sensor_type == 'rain_sensor':
            return 'mdi:water' if self.is_on else 'mdi:water-off'
        return ICON_MAP.get(self._sensor_type)
