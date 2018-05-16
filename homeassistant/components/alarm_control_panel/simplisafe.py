"""
Interfaces with SimpliSafe alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.simplisafe/
"""
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['simplisafe-python==1.0.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'SimpliSafe'
DOMAIN = 'simplisafe'

NOTIFICATION_ID = 'simplisafe_notification'
NOTIFICATION_TITLE = 'SimpliSafe Setup'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SimpliSafe platform."""
    from simplipy.api import SimpliSafeApiInterface, get_systems
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    simplisafe = SimpliSafeApiInterface()
    status = simplisafe.set_credentials(username, password)
    if status:
        hass.data[DOMAIN] = simplisafe
        locations = get_systems(simplisafe)
        for location in locations:
            add_devices([SimpliSafeAlarm(location, name, code)])
    else:
        message = 'Failed to log into SimpliSafe. Check credentials.'
        _LOGGER.error(message)
        hass.components.persistent_notification.create(
            message,
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    def logout(event):
        """Logout of the SimpliSafe API."""
        hass.data[DOMAIN].logout()

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, logout)


class SimpliSafeAlarm(alarm.AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, simplisafe, name, code):
        """Initialize the SimpliSafe alarm."""
        self.simplisafe = simplisafe
        self._name = name
        self._code = str(code) if code else None

    @property
    def name(self):
        """Return the name of the device."""
        if self._name is not None:
            return self._name
        return 'Alarm {}'.format(self.simplisafe.location_id())

    @property
    def code_format(self):
        """Return one or more characters if code is defined."""
        return None if self._code is None else '.+'

    @property
    def state(self):
        """Return the state of the device."""
        status = self.simplisafe.state()
        if status == 'off':
            state = STATE_ALARM_DISARMED
        elif status == 'home':
            state = STATE_ALARM_ARMED_HOME
        elif status == 'away':
            state = STATE_ALARM_ARMED_AWAY
        else:
            state = STATE_UNKNOWN
        return state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'alarm': self.simplisafe.alarm(),
            'co': self.simplisafe.carbon_monoxide(),
            'fire': self.simplisafe.fire(),
            'flood': self.simplisafe.flood(),
            'last_event': self.simplisafe.last_event(),
            'temperature': self.simplisafe.temperature(),
        }

    def update(self):
        """Update alarm status."""
        self.simplisafe.update()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return
        self.simplisafe.set_state('off')
        _LOGGER.info("SimpliSafe alarm disarming")

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return
        self.simplisafe.set_state('home')
        _LOGGER.info("SimpliSafe alarm arming home")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return
        self.simplisafe.set_state('away')
        _LOGGER.info("SimpliSafe alarm arming away")

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check
