"""
A component to monitor Uptime Robot monitors.

For more details about this component, please refer to the documentation at
https://www.home-assistant.io/components/sensor.uptimerobot
"""
import logging
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyuptimerobot==0.0.4']

ATTR_TARGET = 'target'
ATTR_MONITORID = 'monitor id'
ATTR_COMPONENT = 'component'
ATTR_COMPONENT_VERSION = 'component_version'

SCAN_INTERVAL = timedelta(seconds=30)

ICON = 'mdi:server'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the Uptime Robot sensors."""
    from pyuptimerobot import UptimeRobot
    uptimerobot = UptimeRobot()
    apikey = config.get(CONF_API_KEY)
    monitors = uptimerobot.getMonitors(apikey)
    _LOGGER.debug(monitors)
    dev = []
    if not monitors:
        _LOGGER.critical("Something terrible happend :(")
        retval = False
    else:
        for monitor in monitors['monitors']:
            _LOGGER.debug(monitor)
            monitorid = monitor['id']
            name = monitor['friendly_name']
            target = monitor['url']
            dev.append(UptimeRobotSensor(apikey, monitorid, name, target))
        add_devices_callback(dev, True)
        retval = True
    return retval


class UptimeRobotSensor(Entity):
    """Representation of a Uptime Robot sensor."""

    def __init__(self, apikey, monitorid, name, target):
        """Initialize the sensor."""
        self._name = name
        self._monitorid = monitorid
        self._apikey = apikey
        self._target = target
        self.update()

    def update(self):
        """Get the latest state of the sensor."""
        from pyuptimerobot import UptimeRobot
        uptimerobot = UptimeRobot()

        monitor = uptimerobot.getMonitors(self._apikey, str(self._monitorid))
        if not monitor:
            _LOGGER.debug("Failed to get new state, trying again later.")
            return False
        else:
            monitorinfo = monitor['monitors'][0]
            state = monitorinfo['status']
            if state == 2:
                self._state = 'Online'
            else:
                self._state = 'Offline'

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
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_TARGET: self._target,
            ATTR_MONITORID: self._monitorid,
        }
