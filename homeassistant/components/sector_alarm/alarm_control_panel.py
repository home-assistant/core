import logging
from homeassistant.components.sector_alarm import DOMAIN as SECTOR_DOMAIN
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_PENDING,
)

import homeassistant.components.sector_alarm as sector_alarm

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Initialition of the platform."""
    sector_connection = hass.data.get(SECTOR_DOMAIN)

    if sector_connection is None:
        _LOGGER.error("SECTOR_DOMAIN is empty")
        return

    code = discovery_info[sector_alarm.CONF_CODE]
    panel_id = discovery_info[sector_alarm.CONF_ALARM_ID]

    async_add_entities([SectorAlarmPanel(sector_connection, panel_id, code)])


class SectorAlarmPanel(alarm.AlarmControlPanel):
    """Get the alarm status, and arm/disarm alarm."""

    def __init__(self, sectorConnect, alarmId, code):
        self._alarmid = alarmId
        self._code = code
        self._sectorconnect = sectorConnect
        self._state = ""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Sector Alarm {}".format(self._alarmid)

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

        return "unknown"

    async def async_alarm_disarm(self, code=None):
        """Turn off the alarm."""
        _LOGGER.debug("Trying to disarm Sector Alarm")
        status = self._sectorconnect.Disarm()
        if status:
            _LOGGER.debug("Disarmed Sector Alarm")

    async def async_alarm_arm_home(self, code=None):
        """Partial turn on the alarm."""
        _LOGGER.debug("Trying to partial arm Sector Alarm")
        status = self._sectorconnect.ArmPartial()
        if status:
            _LOGGER.debug("Sector Alarm partial armed")

    async def async_alarm_arm_away(self, code=None):
        """Fully turn on the alarm."""
        _LOGGER.debug("Trying to arm Sector Alarm")
        status = self._sectorconnect.Arm()
        if status:
            _LOGGER.debug("Sector Alarm armed")

    async def async_update(self):
        """Update function for alarm status."""
        self._state = self._sectorconnect.AlarmStatus()
