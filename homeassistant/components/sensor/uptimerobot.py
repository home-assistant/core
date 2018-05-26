"""A component to monitor Uptime Robot monitors.

For more details about this component, please refer to the documentation at
https://www.home-assistant.io/components/sensor.uptimerobot
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyuptimerobot==0.0.4']

_LOGGER = logging.getLogger(__name__)

ATTR_TARGET = 'target'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Uptime Robot sensors."""
    from pyuptimerobot import UptimeRobot

    up_robot = UptimeRobot()
    apikey = config.get(CONF_API_KEY)
    monitors = up_robot.getMonitors(apikey)

    devices = []
    if not monitors or monitors.get('stat') != 'ok':
        error = monitors.get('error', {})
        _LOGGER.error(error.get('message', 'Something terrible happend :('))
        return False

    for monitor in monitors['monitors']:
        devices.append(UptimeRobotSensor(
            apikey, up_robot, monitorid=monitor['id'],
            name=monitor['friendly_name'], target=monitor['url']))

    add_devices(devices, True)
    return True


class UptimeRobotSensor(Entity):
    """Representation of a Uptime Robot sensor."""

    def __init__(self, apikey, up_robot, monitorid, name, target):
        """Initialize the sensor."""
        self._apikey = apikey
        self._monitorid = str(monitorid)
        self._name = name
        self._target = target
        self._up_robot = up_robot
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:server'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_TARGET: self._target,
        }

    def update(self):
        """Get the latest state of the sensor."""
        monitor = self._up_robot.getMonitors(self._apikey, self._monitorid)
        if not monitor or monitor.get('stat') != 'ok':
            _LOGGER.debug("Failed to get new state, trying again later.")
            return False

        status = monitor['monitors'][0]['status']
        self._state = 'Online' if status == 2 else 'Offline'
