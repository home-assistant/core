"""Support for e-connect Elmo alarm panel."""

import logging

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    AlarmControlPanel,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_ARMING_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the e-connect Elmo alarm control panel devices."""
    if discovery_info is None:
        return

    device = ElmoAlarmPanel(hass.data[DOMAIN], "Alarm Panel")
    async_add_entities([device])


class ElmoAlarmPanel(AlarmControlPanel):
    """Representation of an e-connect Elmo alarm panel."""

    def __init__(self, client, name):
        """Initialize the alarm panel."""
        self._client = client
        self._name = name
        self._state = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_ARMING_STATE_CHANGED, self._handle_arming_state_change
        )

    @callback
    def _handle_arming_state_change(self, arming_state):
        """Handle arming state update."""
        self._state = arming_state
        self.async_schedule_update_ha_state()

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
        return FORMAT_NUMBER

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Return the list of supported features."""

        return (
            SUPPORT_ALARM_ARM_HOME
            | SUPPORT_ALARM_ARM_AWAY
            | SUPPORT_ALARM_TRIGGER
            | SUPPORT_ALARM_ARM_NIGHT
            | SUPPORT_ALARM_ARM_CUSTOM_BYPASS
        )

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""

        with self._client.lock(code) as client:
            client.disarm()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""

        with self._client.lock(code) as client:
            client.arm_sector(self._client.states[STATE_ALARM_ARMED_AWAY])

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""

        with self._client.lock(code) as client:
            client.arm_sector(self._client.states[STATE_ALARM_ARMED_HOME])

    async def async_alarm_arm_night(self, code=None):
        """Send arm home command."""

        with self._client.lock(code) as client:
            client.arm_sector(self._client.states[STATE_ALARM_ARMED_NIGHT])

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm home command."""

        with self._client.lock(code) as client:
            client.arm_sector(self._client.states[STATE_ALARM_ARMED_CUSTOM_BYPASS])

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state()
