"""Support for Concord232 alarm control panels."""
import datetime
import logging

from concord232 import client as concord232_client
import requests
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
    CONF_MODE,
    CONF_NAME,
    CONF_PORT,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "CONCORD232"
DEFAULT_PORT = 5007
DEFAULT_MODE = "audible"

SCAN_INTERVAL = datetime.timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Concord232 alarm control panel platform."""
    name = config[CONF_NAME]
    code = config.get(CONF_CODE)
    mode = config[CONF_MODE]
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    url = f"http://{host}:{port}"

    try:
        add_entities([Concord232Alarm(url, name, code, mode)], True)
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to Concord232: %s", str(ex))


class Concord232Alarm(alarm.AlarmControlPanelEntity):
    """Representation of the Concord232-based alarm panel."""

    def __init__(self, url, name, code, mode):
        """Initialize the Concord232 alarm panel."""

        self._state = None
        self._name = name
        self._code = code
        self._mode = mode
        self._url = url
        self._alarm = concord232_client.Client(self._url)
        self._alarm.partitions = self._alarm.list_partitions()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """Return the characters if code is defined."""
        return alarm.FORMAT_NUMBER

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def update(self):
        """Update values from API."""
        try:
            part = self._alarm.list_partitions()[0]
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error(
                "Unable to connect to %(host)s: %(reason)s",
                dict(host=self._url, reason=ex),
            )
            return
        except IndexError:
            _LOGGER.error("Concord232 reports no partitions")
            return

        if part["arming_level"] == "Off":
            self._state = STATE_ALARM_DISARMED
        elif "Home" in part["arming_level"]:
            self._state = STATE_ALARM_ARMED_HOME
        else:
            self._state = STATE_ALARM_ARMED_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, STATE_ALARM_DISARMED):
            return
        self._alarm.disarm(code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_HOME):
            return
        if self._mode == "silent":
            self._alarm.arm("stay", "silent")
        else:
            self._alarm.arm("stay")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_AWAY):
            return
        self._alarm.arm("away")

    def _validate_code(self, code, state):
        """Validate given code."""
        if self._code is None:
            return True
        if isinstance(self._code, str):
            alarm_code = self._code
        else:
            alarm_code = self._code.render(from_state=self._state, to_state=state)
        check = not alarm_code or code == alarm_code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
        return check
