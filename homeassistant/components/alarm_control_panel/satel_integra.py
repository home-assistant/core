"""
Support for Satel Integra alarm, using ETHM module: https://www.satel.pl/en/ .

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.satel_integra/
"""
import asyncio
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.satel_integra import (
    CONF_ARM_HOME_MODE, DATA_SATEL, SIGNAL_PANEL_MESSAGE)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['satel_integra']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up for Satel Integra alarm panels."""
    if not discovery_info:
        return

    device = SatelIntegraAlarmPanel(
        "Alarm Panel", discovery_info.get(CONF_ARM_HOME_MODE))
    async_add_devices([device])


class SatelIntegraAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an AlarmDecoder-based alarm panel."""

    def __init__(self, name, arm_home_mode):
        """Initialize the alarm panel."""
        self._name = name
        self._state = None
        self._arm_home_mode = arm_home_mode

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_PANEL_MESSAGE, self._message_callback)

    @callback
    def _message_callback(self, message):
        """Handle received messages."""
        if message != self._state:
            self._state = message
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.warning("Ignoring alarm status message, same state")

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
        return '^\\d{4,6}$'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @asyncio.coroutine
    def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if code:
            yield from self.hass.data[DATA_SATEL].disarm(code)

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if code:
            yield from self.hass.data[DATA_SATEL].arm(code)

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if code:
            yield from self.hass.data[DATA_SATEL].arm(
                code, self._arm_home_mode)
