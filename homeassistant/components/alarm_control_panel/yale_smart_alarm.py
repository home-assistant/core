"""
Yale Smart Alarm client for interacting with the Yale Smart Alarm System API.

For more details about this platform, please refer to the documentation at
https://github.com/domwillcode/yale-smart-alarm-client
"""

import asyncio
import logging

import homeassistant.components.alarm_control_panel as alarm
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_NAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_UNKNOWN)

REQUIREMENTS = ['yalesmartalarmclient==0.1.2']

CONF_AREA_ID = 'area_id'
CONF_ALLOW_DISARM = 'allow_disarm'

YALE_SMART_ALARM_DOMAIN = 'yale_smart_alarm'
DEFAULT_NAME = 'Yale Smart Alarm'

DEFAULT_AREA_ID = '1'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
    vol.Optional(CONF_ALLOW_DISARM): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the alarm platform."""
    if YALE_SMART_ALARM_DOMAIN not in hass.data:
        hass.data[YALE_SMART_ALARM_DOMAIN] = []

    alarm_panel = YaleAlarmDevice(
        config.get(CONF_NAME),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_AREA_ID))

    hass.data[YALE_SMART_ALARM_DOMAIN].append(alarm_panel)

    async_add_devices([alarm_panel], True)


class YaleAlarmDevice(alarm.AlarmControlPanel):
    """Represent a Yale Smart Alarm."""

    def __init__(self, name, username, password, area_id):
        """Initialize the Yale Alarm Device."""
        _LOGGER.debug("Setting up Yale Smart Alarm")
        self._name = name
        self._username = username
        self._password = password
        self._state = STATE_UNKNOWN

        from yalesmartalarmclient.client import YaleSmartAlarmClient

        self._client = YaleSmartAlarmClient(
            username,
            password,
            area_id)

        _LOGGER.debug("Yale Smart Alarm client created and authenticated")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Return the state of the device."""
        from yalesmartalarmclient.client import (YALE_STATE_DISARM,
                                                 YALE_STATE_ARM_PARTIAL,
                                                 YALE_STATE_ARM_FULL)

        status = self._client.get_armed_status()

        if status == YALE_STATE_DISARM:
            state = STATE_ALARM_DISARMED
        elif status == YALE_STATE_ARM_PARTIAL:
            state = STATE_ALARM_ARMED_HOME
        elif status == YALE_STATE_ARM_FULL:
            state = STATE_ALARM_ARMED_AWAY
        else:
            state = STATE_UNKNOWN

        self._state = state

    @asyncio.coroutine
    def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        self._client.disarm()

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._client.arm_partial()

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._client.arm_full()

    @asyncio.coroutine
    def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._client.arm_partial()
