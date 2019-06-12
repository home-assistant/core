"""Support for Satel Integra alarm, using ETHM module."""
import asyncio
import logging
from collections import OrderedDict

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    CONF_ARM_HOME_MODE, CONF_DEVICE_PARTITIONS, DATA_SATEL, CONF_ZONE_NAME,
    SIGNAL_PANEL_MESSAGE)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up for Satel Integra alarm panels."""
    if not discovery_info:
        return

    configured_partitions = discovery_info[CONF_DEVICE_PARTITIONS]
    controller = hass.data[DATA_SATEL]

    devices = []

    for partition_num, device_config_data in configured_partitions.items():
        zone_name = device_config_data[CONF_ZONE_NAME]
        arm_home_mode = device_config_data.get(CONF_ARM_HOME_MODE)
        device = SatelIntegraAlarmPanel(
            controller,
            zone_name,
            arm_home_mode,
            partition_num)
        devices.append(device)

    async_add_entities(devices)


class SatelIntegraAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an AlarmDecoder-based alarm panel."""

    def __init__(self, controller, name, arm_home_mode, partition_id):
        """Initialize the alarm panel."""
        self._name = name
        self._state = None
        self._arm_home_mode = arm_home_mode
        self._partition_id = partition_id
        self._satel = controller

    async def async_added_to_hass(self):
        """Update alarm status and register callbacks for future updates."""
        _LOGGER.debug("Starts listening for panel messages")
        self._update_alarm_status()
        async_dispatcher_connect(
            self.hass, SIGNAL_PANEL_MESSAGE, self._update_alarm_status)

    @callback
    def _update_alarm_status(self):
        """Handle alarm status update."""
        state = self._read_alarm_state()
        _LOGGER.debug("Got status update, current status: %s", state)
        if state != self._state:
            self._state = state
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.debug("Ignoring alarm status message, same state")

    def _read_alarm_state(self):
        """Read current status of the alarm and translate it into HA status."""
        from satel_integra.satel_integra import AlarmState

        # Default - disarmed:
        hass_alarm_status = STATE_ALARM_DISARMED

        if not self._satel.connected:
            return None

        state_map = OrderedDict([
            (AlarmState.TRIGGERED, STATE_ALARM_TRIGGERED),
            (AlarmState.TRIGGERED_FIRE, STATE_ALARM_TRIGGERED),
            (AlarmState.ENTRY_TIME, STATE_ALARM_PENDING),
            (AlarmState.ARMED_MODE3, STATE_ALARM_ARMED_HOME),
            (AlarmState.ARMED_MODE2, STATE_ALARM_ARMED_HOME),
            (AlarmState.ARMED_MODE1, STATE_ALARM_ARMED_HOME),
            (AlarmState.ARMED_MODE0, STATE_ALARM_ARMED_AWAY),
            (AlarmState.EXIT_COUNTDOWN_OVER_10, STATE_ALARM_PENDING),
            (AlarmState.EXIT_COUNTDOWN_UNDER_10, STATE_ALARM_PENDING)
        ])
        _LOGGER.debug("State map of Satel: %s", self._satel.partition_states)

        for satel_state, ha_state in state_map.items():
            if satel_state in self._satel.partition_states and\
               self._partition_id in self._satel.partition_states[satel_state]:
                hass_alarm_status = ha_state
                break

        return hass_alarm_status

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
        if not code:
            _LOGGER.debug("Code was empty or None")
            return

        clear_alarm_necessary = self._state == STATE_ALARM_TRIGGERED

        _LOGGER.debug("Disarming, self._state: %s", self._state)

        await self._satel.disarm(code, [self._partition_id])

        if clear_alarm_necessary:
            # Wait 1s before clearing the alarm
            await asyncio.sleep(1)
            await self._satel.clear_alarm(code, [self._partition_id])

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        _LOGGER.debug("Arming away")

        if code:
            await self._satel.arm(code, [self._partition_id])

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        _LOGGER.debug("Arming home")

        if code:
            await self._satel.arm(
                code, [self._partition_id], self._arm_home_mode)
