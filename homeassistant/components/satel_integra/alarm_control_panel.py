"""Support for Satel Integra alarm, using ETHM module."""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.satel_integra import (
    CONF_ARM_HOME_MODE, CONF_DEVICE_PARTITION, DATA_SATEL, SIGNAL_PANEL_MESSAGE)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['satel_integra']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up for Satel Integra alarm panels."""
    if not discovery_info:
        return

    device = SatelIntegraAlarmPanel(
        "Alarm Panel", discovery_info.get(CONF_ARM_HOME_MODE),discovery_info.get(CONF_DEVICE_PARTITION) )
    async_add_entities([device])


class SatelIntegraAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an AlarmDecoder-based alarm panel."""

    def __init__(self, name, arm_home_mode, partition_id):
        """Initialize the alarm panel."""
        self._name = name
        self._state = None
        self._arm_home_mode = arm_home_mode
        self._partition_id = partition_id
        _LOGGER.info("Creating AlarmPanel")

    async def async_added_to_hass(self):
        """Update alarm status and register callbacks for future updates."""
        _LOGGER.info("Starts listening for panel messages: async_dispatcher_connect")
        self._update_alarm_status()
        async_dispatcher_connect(
            self.hass, SIGNAL_PANEL_MESSAGE, self._update_alarm_status)

    def _read_alarm_state(self):
        """Read current status of the alarm device and translate it into HA alarm status"""       
        
        from satel_integra.satel_integra import AlarmState
        
        # Default - disarmed:
        hass_alarm_status = STATE_ALARM_DISARMED

        # Hardcoded for now, maybe in the future will make it into configuration variable:
        
        satel_controller = self.hass.data[DATA_SATEL]
        if not satel_controller.connected:
            return STATE_UNKNOWN
        
        state_map = {
                AlarmState.TRIGGERED : STATE_ALARM_TRIGGERED,
                AlarmState.TRIGGERED_FIRE : STATE_ALARM_TRIGGERED,
                AlarmState.ARMED_MODE0 : STATE_ALARM_ARMED_AWAY, 
                AlarmState.ARMED_MODE1 : STATE_ALARM_ARMED_HOME,
                AlarmState.ARMED_MODE2 : STATE_ALARM_ARMED_HOME,
                AlarmState.ARMED_MODE3 : STATE_ALARM_ARMED_HOME,
        }

        for satel_state, ha_state in state_map.items():
            if satel_state in satel_controller.partition_states and self._partition_id in satel_controller.partition_states[satel_state]:
                    hass_alarm_status = ha_state
                    break
        
        # status = self.hass.data[DATA_SATEL].status 

        # if status == AlarmState.ARMED_MODE0:
        #     hass_alarm_status = STATE_ALARM_ARMED_AWAY

        # elif status in [
        #         AlarmState.ARMED_MODE0,
        #         AlarmState.ARMED_MODE1,
        #         AlarmState.ARMED_MODE2,
        #         AlarmState.ARMED_MODE3
        # ]:
        #     hass_alarm_status = STATE_ALARM_ARMED_HOME

        # elif status in [AlarmState.TRIGGERED, AlarmState.TRIGGERED_FIRE]:
        #     hass_alarm_status = STATE_ALARM_TRIGGERED

        # elif status == AlarmState.DISARMED:
        #     hass_alarm_status = STATE_ALARM_DISARMED
        return hass_alarm_status
        
    @callback
    def _update_alarm_status(self, message=None):
        """Handle received messages."""
        state = self._read_alarm_state()
        _LOGGER.info("Got status update, current status: %s", state)
        if state != self._state:
            self._state = state
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug("Ignoring alarm status message, same state")

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def code_format(self):
        """Return the regex for code format or None if no code is required."""
        return alarm.FORMAT_NUMBER

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if code:
            await self.hass.data[DATA_SATEL].disarm(code)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if code:
            await self.hass.data[DATA_SATEL].arm(code)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if code:
            await self.hass.data[DATA_SATEL].arm(
                code, self._arm_home_mode)
