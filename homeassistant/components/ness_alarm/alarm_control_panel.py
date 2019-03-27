"""
Support for Ness D8X/D16X alarm panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.ness_alarm/
"""

import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMING, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_NESS, SIGNAL_ARMING_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ness_alarm']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Ness Alarm alarm control panel devices."""
    if discovery_info is None:
        return

    device = NessAlarmPanel(hass.data[DATA_NESS], 'Alarm Panel')
    async_add_entities([device])


class NessAlarmPanel(alarm.AlarmControlPanel):
    """Representation of a Ness alarm panel."""

    def __init__(self, client, name):
        """Initialize the alarm panel."""
        self._client = client
        self._name = name
        self._state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_ARMING_STATE_CHANGED,
            self._handle_arming_state_change)

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
        await self._client.disarm(code)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._client.arm_away(code)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self._client.arm_home(code)

    async def async_alarm_trigger(self, code=None):
        """Send trigger/panic command."""
        await self._client.panic(code)

    @callback
    def _handle_arming_state_change(self, arming_state):
        """Handle arming state update."""
        from nessclient import ArmingState

        if arming_state == ArmingState.UNKNOWN:
            self._state = None
        elif arming_state == ArmingState.DISARMED:
            self._state = STATE_ALARM_DISARMED
        elif arming_state == ArmingState.ARMING:
            self._state = STATE_ALARM_ARMING
        elif arming_state == ArmingState.EXIT_DELAY:
            self._state = STATE_ALARM_ARMING
        elif arming_state == ArmingState.ARMED:
            self._state = STATE_ALARM_ARMED_AWAY
        elif arming_state == ArmingState.ENTRY_DELAY:
            self._state = STATE_ALARM_PENDING
        elif arming_state == ArmingState.TRIGGERED:
            self._state = STATE_ALARM_TRIGGERED
        else:
            _LOGGER.warning("Unhandled arming state: %s", arming_state)

        self.async_schedule_update_ha_state()
