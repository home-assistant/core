"""
Interfaces with Egardia / Woonveilig alarm control panel.

For more details about this platform, please refer to
https://home-assistant.io/components/alarm_control_panel.egardia/
"""

import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PORT, CONF_HOST, CONF_PASSWORD, CONF_USERNAME,
    STATE_UNKNOWN, CONF_NAME,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY)
import homeassistant.helpers.config_validation as cv
import homeassistant.exceptions as exc

REQUIREMENTS = ['pythonegardia==1.0.9']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Egardia'
DEFAULT_PORT = '80'
DOMAIN = 'egardia'
NOTIFICATION_ID = 'egardia_notification'
NOTIFICATION_TITLE = 'Egardia'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    })


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Egardia platform."""
    from pythonegardia import egardiadevice
    import requests
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    try:
        egardiasystem = egardiadevice.EgardiaDevice(host, port,
                                                    username, password, "")
    except requests.ConnectionError:
        raise exc.PlatformNotReady()
    except egardiadevice.UnauthorizedError:
        _LOGGER.error("Unable to authorize. Wrong password or username.")
        return False
    add_devices([EgardiaAlarm(name, egardiasystem)])


class EgardiaAlarm(alarm.AlarmControlPanel):
    """Representation of a Egardia alarm."""

    def __init__(self, name, egardiasystem):
        """Initialize object."""
        self._name = name
        self._egardiasystem = egardiasystem
        self._status = STATE_UNKNOWN

    STATES = {
        'ARM': STATE_ALARM_ARMED_AWAY,
        'HOME': STATE_ALARM_ARMED_HOME,
        'DAY HOME': STATE_ALARM_ARMED_HOME,
        'DISARM': STATE_ALARM_DISARMED,
        'UNKNOWN': STATE_UNKNOWN
    }

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._status

    def update(self):
        """Update the alarm status."""
        status = self._egardiasystem.getState()
        self._status = ([v for k, v in self.STATES.items()
                         if status.upper() == k][0])

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._egardiasystem.alarm_disarm()
        _LOGGER.info("Egardia alarm DISARMED")

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._egardiasystem.alarm_arm_home()
        _LOGGER.info("Egardia alarm ARMED HOME")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._egardiasystem.alarm_arm_away()
        _LOGGER.info("Egardia alarm ARMED AWAY")
