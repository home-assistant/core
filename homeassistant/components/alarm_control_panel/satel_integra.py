"""
Support for Satel Integra alarm, using ETHM module. Satel:
https://www.satel.pl/en/

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_satel_integra/
"""
"""
Support for AlarmDecoder-based alarm control panels (Honeywell/DSC).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdecoder/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.components.alarm_control_panel as alarm

from homeassistant.components.satel_integra import (DATA_AD,
                                                    DOMAIN,
                                                    SIGNAL_PANEL_MESSAGE,
                                                    CONF_ARM_HOME_MODE)

from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['satel_integra']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up for AlarmDecoder alarm panels."""


    device = SatelIntegraAlarmPanel("Alarm Panel",
                                    hass,
                                    discovery_info.get(CONF_ARM_HOME_MODE))
    async_add_devices([device])

    return True


class SatelIntegraAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an AlarmDecoder-based alarm panel."""

    def __init__(self, name, hass, arm_home_mode):
        """Initialize the alarm panel."""
        self._display = ""
        self._name = name
        self._state = STATE_UNKNOWN
        self._arm_home_mode = arm_home_mode

        _LOGGER.debug("Setting up panel")

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_PANEL_MESSAGE, self._message_callback)

    @callback
    def _message_callback(self, message):
        _LOGGER.info("Got message: %s", message)

        if message != self._state:
            self._state = message
            self.hass.async_add_job(self.async_update_ha_state())
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
        _LOGGER.debug("alarm_disarm: %s", code)
        if code:
            yield from self.hass.data[DATA_AD].disarm(str(code))

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        _LOGGER.debug("alarm_arm_away: %s", code)
        if code:
            _LOGGER.debug("alarm_arm_away: sending %s", code)
            yield from self.hass.data[DATA_AD].arm(code)

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        _LOGGER.debug("alarm_arm_home: %s", code)
        if code:
            _LOGGER.debug("alarm_arm_home: sending %s", code)
            yield from self.hass.data[DATA_AD].arm(code, self._arm_home_mode)
