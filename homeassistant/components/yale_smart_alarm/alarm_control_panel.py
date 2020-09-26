"""Component for interacting with the Yale Smart Alarm System API."""
import logging

import voluptuous as vol
from yalesmartalarmclient.client import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
    AuthenticationError,
    YaleSmartAlarmClient,
)

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
import homeassistant.helpers.config_validation as cv

CONF_AREA_ID = "area_id"

DEFAULT_NAME = "Yale Smart Alarm"

DEFAULT_AREA_ID = "1"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the alarm platform."""
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    area_id = config[CONF_AREA_ID]

    try:
        client = YaleSmartAlarmClient(username, password, area_id)
    except AuthenticationError:
        _LOGGER.error("Authentication failed. Check credentials")
        return

    add_entities([YaleAlarmDevice(name, client)], True)


class YaleAlarmDevice(AlarmControlPanelEntity):
    """Represent a Yale Smart Alarm."""

    def __init__(self, name, client):
        """Initialize the Yale Alarm Device."""
        self._name = name
        self._client = client
        self._state = None

        self._state_map = {
            YALE_STATE_DISARM: STATE_ALARM_DISARMED,
            YALE_STATE_ARM_PARTIAL: STATE_ALARM_ARMED_HOME,
            YALE_STATE_ARM_FULL: STATE_ALARM_ARMED_AWAY,
        }

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

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
        armed_status = self._client.get_armed_status()

        self._state = self._state_map.get(armed_status)

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._client.disarm()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._client.arm_partial()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._client.arm_full()
