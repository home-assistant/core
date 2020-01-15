"""The Sector Alarm Integration."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.components.sector_alarm import (
    CONF_CODE,
    CONF_ID,
    DOMAIN as SECTOR_DOMAIN,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Initialition of the platform."""
    sector_connection = hass.data.get(SECTOR_DOMAIN)

    code = discovery_info[CONF_CODE]
    panel_id = discovery_info[CONF_ID]

    async_add_entities([SectorAlarmPanel(sector_connection, panel_id, code)])


class SectorAlarmPanel(AlarmControlPanel):
    """Get the alarm status, and arm/disarm alarm."""

    def __init__(self, sector_connect, alarm_id, code):
        """Initialize the service."""
        self._alarm_id = alarm_id
        self._code = code
        self._sector_connect = sector_connect
        self._state = None

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Sector Alarm {self._alarm_id}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state == "ON":
            return STATE_ALARM_ARMED_AWAY

        if self._state == "PARTIAL":
            return STATE_ALARM_ARMED_HOME

        if self._state == "OFF":
            return STATE_ALARM_DISARMED

        if self._state == "pending":
            return STATE_ALARM_PENDING

        return None

    async def async_alarm_disarm(self, code=None):
        """Turn off the alarm."""
        _LOGGER.debug("Trying to disarm Sector Alarm")
        status = self._sector_connect.Disarm()
        if status:
            _LOGGER.debug("Disarmed Sector Alarm")

    async def async_alarm_arm_home(self, code=None):
        """Partial turn on the alarm."""
        _LOGGER.debug("Trying to partial arm Sector Alarm")
        status = self._sector_connect.ArmPartial()
        if status:
            _LOGGER.debug("Sector Alarm partial armed")

    async def async_alarm_arm_away(self, code=None):
        """Fully turn on the alarm."""
        _LOGGER.debug("Trying to arm Sector Alarm")
        status = self._sector_connect.Arm()
        if status:
            _LOGGER.debug("Sector Alarm armed")

    async def async_update(self):
        """Update function for alarm status."""
        self._state = self._sector_connect.AlarmStatus()
