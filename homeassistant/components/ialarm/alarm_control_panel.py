"""Interfaces with iAlarm control panels."""
import logging
import re

from pyialarm import IAlarm
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "iAlarm"


def no_application_protocol(value):
    """Validate that value is without the application protocol."""
    protocol_separator = "://"
    if not value or protocol_separator in value:
        raise vol.Invalid(f"Invalid host, {protocol_separator} is not allowed")

    return value


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): vol.All(cv.string, no_application_protocol),
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_CODE): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an iAlarm control panel."""
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)

    url = f"http://{host}"
    ialarm = IAlarmPanel(name, code, username, password, url)
    add_entities([ialarm], True)


class IAlarmPanel(alarm.AlarmControlPanelEntity):
    """Representation of an iAlarm status."""

    def __init__(self, name, code, username, password, url):
        """Initialize the iAlarm status."""

        self._name = name
        self._code = str(code) if code else None
        self._username = username
        self._password = password
        self._url = url
        self._state = None
        self._client = IAlarm(username, password, url)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and re.search("^\\d+$", self._code):
            return alarm.FORMAT_NUMBER
        return alarm.FORMAT_TEXT

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def update(self):
        """Return the state of the device."""
        status = self._client.get_status()
        _LOGGER.debug("iAlarm status: %s", status)
        if status:
            status = int(status)

        if status == self._client.DISARMED:
            state = STATE_ALARM_DISARMED
        elif status == self._client.ARMED_AWAY:
            state = STATE_ALARM_ARMED_AWAY
        elif status == self._client.ARMED_STAY:
            state = STATE_ALARM_ARMED_HOME
        elif status == self._client.TRIGGERED:
            state = STATE_ALARM_TRIGGERED
        else:
            state = None

        self._state = state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if self._validate_code(code):
            self._client.disarm()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._validate_code(code):
            self._client.arm_away()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if self._validate_code(code):
            self._client.arm_stay()

    def _validate_code(self, code):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered")
        return check
