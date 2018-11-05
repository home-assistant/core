"""
This platform provides alarm control functionality for SimpliSafe.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.simplisafe/
"""
import logging
import re

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.components.simplisafe.const import (
    DATA_CLIENT, DOMAIN, TOPIC_UPDATE)
from homeassistant.const import (
    CONF_CODE, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

ATTR_ALARM_ACTIVE = 'alarm_active'
ATTR_TEMPERATURE = 'temperature'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up a SimpliSafe alarm control panel based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a SimpliSafe alarm control panel based on a config entry."""
    systems = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities([
        SimpliSafeAlarm(system, entry.data.get(CONF_CODE))
        for system in systems
    ], True)


class SimpliSafeAlarm(AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, system, code):
        """Initialize the SimpliSafe alarm."""
        self._async_unsub_dispatcher_connect = None
        self._attrs = {}
        self._code = code
        self._system = system
        self._state = None

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._system.system_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._system.address

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if not self._code:
            return None
        if isinstance(self._code, str) and re.search('^\\d+$', self._code):
            return 'Number'
        return 'Any'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return

        await self._system.set_off()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return

        await self._system.set_home()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return

        await self._system.set_away()

    async def async_update(self):
        """Update alarm status."""
        from simplipy.system import SystemStates

        await self._system.update()

        self._attrs[ATTR_ALARM_ACTIVE] = self._system.alarm_going_off
        if self._system.temperature:
            self._attrs[ATTR_TEMPERATURE] = self._system.temperature

        if self._system.state == SystemStates.error:
            return

        if self._system.state == SystemStates.off:
            self._state = STATE_ALARM_DISARMED
        elif self._system.state in (SystemStates.home,
                                    SystemStates.home_count):
            self._state = STATE_ALARM_ARMED_HOME
        elif self._system.state in (SystemStates.away, SystemStates.away_count,
                                    SystemStates.exit_delay):
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = None
