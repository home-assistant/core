"""
Support for Melnor RainCloud sprinkler water timer.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.raincloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.raincloud import (
    DATA_RAINCLOUD, ICON_MAP, RainCloudEntity, SENSORS)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.icon import icon_for_battery_level

DEPENDENCIES = ['raincloud']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a raincloud device."""
    raincloud = hass.data[DATA_RAINCLOUD].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == 'battery':
            sensors.append(
                RainCloudSensor(raincloud.controller.faucet,
                                sensor_type))
        else:
            # create a sensor for each zone managed by a faucet
            for zone in raincloud.controller.faucet.zones:
                sensors.append(RainCloudSensor(zone, sensor_type))

    add_devices(sensors, True)
    return True


class RainCloudSensor(RainCloudEntity):
    """A sensor implementation for raincloud device."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating RainCloud sensor: %s", self._name)
        if self._sensor_type == 'battery':
            self._state = self.data.battery
        else:
            self._state = getattr(self.data, self._sensor_type)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == 'battery' and self._state is not None:
            return icon_for_battery_level(battery_level=int(self._state),
                                          charging=False)
        return ICON_MAP.get(self._sensor_type)
