"""
Support for Vanderbilt (formerly Siemens) SPC alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.spc/
"""
import asyncio
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.spc import (
    SpcWebGateway, ATTR_DISCOVER_AREAS, DATA_API, DATA_REGISTRY)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN)


_LOGGER = logging.getLogger(__name__)

SPC_AREA_MODE_TO_STATE = {'0': STATE_ALARM_DISARMED,
                          '1': STATE_ALARM_ARMED_HOME,
                          '3': STATE_ALARM_ARMED_AWAY}


def _get_alarm_state(spc_mode):
    return SPC_AREA_MODE_TO_STATE.get(spc_mode, STATE_UNKNOWN)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up the SPC alarm control panel platform."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_AREAS] is None):
        return

    entities = [SpcAlarm(hass=hass,
                         area_id=area['id'],
                         name=area['name'],
                         state=_get_alarm_state(area['mode']))
                for area in discovery_info[ATTR_DISCOVER_AREAS]]

    async_add_entities(entities)


class SpcAlarm(alarm.AlarmControlPanel):
    """Represents the SPC alarm panel."""

    def __init__(self, hass, area_id, name, state):
        """Initialize the SPC alarm panel."""
        self._hass = hass
        self._area_id = area_id
        self._name = name
        self._state = state
        self._api = hass.data[DATA_API]

        hass.data[DATA_REGISTRY].register_alarm_device(area_id, self)

    @asyncio.coroutine
    def async_update_from_spc(self, state):
        """Update the alarm panel with a new state."""
        self._state = state
        yield from self.async_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @asyncio.coroutine
    def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        yield from self._api.send_area_command(
            self._area_id, SpcWebGateway.AREA_COMMAND_UNSET)

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        yield from self._api.send_area_command(
            self._area_id, SpcWebGateway.AREA_COMMAND_PART_SET)

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        yield from self._api.send_area_command(
            self._area_id, SpcWebGateway.AREA_COMMAND_SET)
