"""
Interfaces with Alarm.com alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdotcom/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyalarmdotcom==0.3.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Alarm.com'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CODE): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Alarm.com control panel."""
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    alarmdotcom = AlarmDotCom(hass, name, code, username, password)
    yield from alarmdotcom.async_login()
    async_add_devices([alarmdotcom])


class AlarmDotCom(alarm.AlarmControlPanel):
    """Representation of an Alarm.com status."""

    def __init__(self, hass, name, code, username, password):
        """Initialize the Alarm.com status."""
        from pyalarmdotcom import Alarmdotcom
        _LOGGER.debug('Setting up Alarm.com...')
        self._hass = hass
        self._name = name
        self._code = str(code) if code else None
        self._username = username
        self._password = password
        self._websession = async_get_clientsession(self._hass)
        self._state = STATE_UNKNOWN
        self._alarm = Alarmdotcom(
            username, password, self._websession, hass.loop)

    @asyncio.coroutine
    def async_login(self):
        """Login to Alarm.com."""
        yield from self._alarm.async_login()

    @asyncio.coroutine
    def async_update(self):
        """Fetch the latest state."""
        yield from self._alarm.async_update()
        return self._alarm.state

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._name

    @property
    def code_format(self):
        """Return one or more characters if code is defined."""
        return None if self._code is None else '.+'

    @property
    def state(self):
        """Return the state of the device."""
        if self._alarm.state.lower() == 'disarmed':
            return STATE_ALARM_DISARMED
        elif self._alarm.state.lower() == 'armed stay':
            return STATE_ALARM_ARMED_HOME
        elif self._alarm.state.lower() == 'armed away':
            return STATE_ALARM_ARMED_AWAY
        return STATE_UNKNOWN

    @asyncio.coroutine
    def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if self._validate_code(code):
            yield from self._alarm.async_alarm_disarm()

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm hom command."""
        if self._validate_code(code):
            yield from self._alarm.async_alarm_arm_home()

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._validate_code(code):
            yield from self._alarm.async_alarm_arm_away()

    def _validate_code(self, code):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered")
        return check
