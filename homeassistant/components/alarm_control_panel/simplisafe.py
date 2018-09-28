"""
Interfaces with SimpliSafe alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.simplisafe/
"""
import logging
import re

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA, AlarmControlPanel)
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN)
from homeassistant.helpers import aiohttp_client, config_validation as cv

REQUIREMENTS = ['simplisafe-python==3.0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'SimpliSafe'

ATTR_ALARM_ACTIVE = "alarm_active"
ATTR_TEMPERATURE = "temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the SimpliSafe platform."""
    from simplipy import get_systems
    from simplipy.errors import SimplipyError

    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)
    name = config[CONF_NAME]
    code = config.get(CONF_CODE)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        systems = await get_systems(username, password, websession)
    except SimplipyError as err:
        _LOGGER.error("There was an error during setup: %s", err)
        return

    async_add_entities(
        [SimpliSafeAlarm(system, name, code) for system in systems], True)


class SimpliSafeAlarm(AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, simplisafe, name, code):
        """Initialize the SimpliSafe alarm."""
        self._attrs = {}
        self._code = str(code) if code else None
        self._name = name
        self._simplisafe = simplisafe
        self._state = STATE_UNKNOWN

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._simplisafe.system_id

    @property
    def name(self):
        """Return the name of the device."""
        if self._name:
            return self._name
        return 'Alarm {}'.format(self._simplisafe.system_id)

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if not self._code:
            return None
        if isinstance(self._code, str) and re.search('^\\d+$', self._code):
            return 'Number'
        return 'Any'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return

        await self._simplisafe.set_off()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return

        await self._simplisafe.set_home()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return

        await self._simplisafe.set_away()

    async def async_update(self):
        """Update alarm status."""
        await self._simplisafe.update()

        if self._simplisafe.state == self._simplisafe.SystemStates.off:
            self._state = STATE_ALARM_DISARMED
        elif self._simplisafe.state in (
                self._simplisafe.SystemStates.home,
                self._simplisafe.SystemStates.home_count):
            self._state = STATE_ALARM_ARMED_HOME
        elif self._simplisafe.state in (
                self._simplisafe.SystemStates.away,
                self._simplisafe.SystemStates.away_count,
                self._simplisafe.SystemStates.exit_delay):
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = STATE_UNKNOWN

        self._attrs[ATTR_ALARM_ACTIVE] = self._simplisafe.alarm_going_off
        if self._simplisafe.temperature:
            self._attrs[ATTR_TEMPERATURE] = self._simplisafe.temperature
