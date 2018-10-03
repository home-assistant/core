"""
Interfaces with Alarm.com alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdotcom/
"""
import logging
import re

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyalarmdotcom==0.3.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Alarm.com'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CODE): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a Alarm.com control panel."""
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    alarmdotcom = AlarmDotCom(hass, name, code, username, password)
    await alarmdotcom.async_login()
    async_add_entities([alarmdotcom])


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

    async def async_login(self):
        """Login to Alarm.com."""
        await self._alarm.async_login()

    async def async_update(self):
        """Fetch the latest state."""
        await self._alarm.async_update()
        return self._alarm.state

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._name

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and re.search('^\\d+$', self._code):
            return 'Number'
        return 'Any'

    @property
    def state(self):
        """Return the state of the device."""
        if self._alarm.state.lower() == 'disarmed':
            return STATE_ALARM_DISARMED
        if self._alarm.state.lower() == 'armed stay':
            return STATE_ALARM_ARMED_HOME
        if self._alarm.state.lower() == 'armed away':
            return STATE_ALARM_ARMED_AWAY
        return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'sensor_status': self._alarm.sensor_status
        }

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if self._validate_code(code):
            await self._alarm.async_alarm_disarm()

    async def async_alarm_arm_home(self, code=None):
        """Send arm hom command."""
        if self._validate_code(code):
            await self._alarm.async_alarm_arm_home()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._validate_code(code):
            await self._alarm.async_alarm_arm_away()

    def _validate_code(self, code):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered")
        return check
