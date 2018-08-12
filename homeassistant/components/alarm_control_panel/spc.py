"""
Support for Vanderbilt (formerly Siemens) SPC alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.spc/
"""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.spc import (
    ATTR_DISCOVER_AREAS, DATA_API, DATA_REGISTRY)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)


def _get_alarm_state(spc_mode):
    """Get the alarm state."""
    from pyspcwebgw.const import AreaMode

    mode_to_state = {
        AreaMode.UNSET: STATE_ALARM_DISARMED,
        AreaMode.PART_SET_A: STATE_ALARM_ARMED_HOME,
        AreaMode.PART_SET_B: STATE_ALARM_ARMED_NIGHT,
        AreaMode.FULL_SET: STATE_ALARM_ARMED_AWAY,
    }
    return mode_to_state.get(spc_mode, STATE_UNKNOWN)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the SPC alarm control panel platform."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_AREAS] is None):
        return

    async_add_entities([SpcAlarm(area=area)
                        for area in discovery_info[ATTR_DISCOVER_AREAS]])


class SpcAlarm(alarm.AlarmControlPanel):
    """Representation of the SPC alarm panel."""

    def __init__(self, area):
        """Initialize the SPC alarm panel."""
        self._area = area

    async def async_added_to_hass(self):
        """Call for adding new entities."""
        self.hass.data[DATA_REGISTRY].register_alarm_device(
            self._area.id, self)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._area.name

    @property
    def changed_by(self):
        """Return the user the last change was triggered by."""
        return self._area.last_changed_by

    @property
    def state(self):
        """Return the state of the device."""
        return _get_alarm_state(self._area.mode)

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        from pyspcwebgw.const import AreaMode
        self.hass.data[DATA_API].change_mode(area=self._area,
                                             new_mode=AreaMode.UNSET)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        from pyspcwebgw.const import AreaMode
        self.hass.data[DATA_API].change_mode(area=self._area,
                                             new_mode=AreaMode.PART_SET_A)

    async def async_alarm_arm_night(self, code=None):
        """Send arm home command."""
        from pyspcwebgw.const import AreaMode
        self.hass.data[DATA_API].change_mode(area=self._area,
                                             new_mode=AreaMode.PART_SET_B)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        from pyspcwebgw.const import AreaMode
        self.hass.data[DATA_API].change_mode(area=self._area,
                                             new_mode=AreaMode.FULL_SET)
