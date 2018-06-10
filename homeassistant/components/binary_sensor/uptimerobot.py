"""A component to monitor Uptime Robot monitors.

For more details about this component, please refer to the documentation at
https://www.home-assistant.io/components/binary_sensor.uptimerobot
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyuptimerobot==0.0.4']

_LOGGER = logging.getLogger(__name__)

ATTR_TARGET = 'target'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Uptime Robot binary_sensors."""
    from pyuptimerobot import UptimeRobot

    up_robot = UptimeRobot()
    apikey = config.get(CONF_API_KEY)
    monitors = up_robot.getMonitors(apikey)

    devices = []
    if not monitors or monitors.get('stat') != 'ok':
        _LOGGER.error('Error connecting to uptime robot.')
        return

    for monitor in monitors['monitors']:
        devices.append(UptimeRobotBinarySensor(
            apikey, up_robot, monitorid=monitor['id'],
            name=monitor['friendly_name'], target=monitor['url']))

    add_devices(devices, True)


class UptimeRobotBinarySensor(BinarySensorDevice):
    """Representation of a Uptime Robot binary_sensor."""

    def __init__(self, apikey, up_robot, monitorid, name, target):
        """Initialize the binary_sensor."""
        self._apikey = apikey
        self._monitorid = str(monitorid)
        self._name = name
        self._target = target
        self._up_robot = up_robot
        self._state = None

    @property
    def name(self):
        """Return the name of the binary_sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'connectivity'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary_sensor."""
        return {
            ATTR_TARGET: self._target,
        }

    def update(self):
        """Get the latest state of the binary_sensor."""
        monitor = self._up_robot.getMonitors(self._apikey, self._monitorid)
        if not monitor or monitor.get('stat') != 'ok':
            _LOGGER.debug("Failed to get new state, trying again later.")
            return
        status = monitor['monitors'][0]['status']
        self._state = 1 if status == 2 else 0
