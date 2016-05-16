"""
Support for Envisalink-based alarm control panels (Honeywell/DSC).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.envisalink/
"""
import logging

import requests

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.envisalink import (EVL_CONTROLLER, EnvisalinkDevice, SIGNAL_PARTITION_UPDATE)
from homeassistant.util import convert
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN)

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Envisalink alarm panels."""
    _configuredPartitions = discovery_info['partitions']
    add_devices_callback(EnvisalinkAlarm(convert(_configuredPartitions[partNum]['name'], str, str.format("Partition #{0}", partNum)),
                                                 EVL_CONTROLLER.alarm_state['partition'][partNum], EVL_CONTROLLER)
                         for partNum in _configuredPartitions)
    return True

class EnvisalinkAlarm(EnvisalinkDevice, alarm.AlarmControlPanel):
    """Represents the Envisalink-based alarm panel."""

    def __init__(self, alarmName, info, controller):
        """Initialize the alarm panel."""
        from pydispatch import dispatcher
        
        _LOGGER.info('Setting up alarm: ' + alarmName)
        EnvisalinkDevice.__init__(self, alarmName, info, controller)
        dispatcher.connect(self._update_callback, signal=SIGNAL_PARTITION_UPDATE, sender=dispatcher.Any)

    def _update_callback(self):
        self.update_ha_state()

    @property
    def code_format(self):
        """The characters if code is defined."""
        return '[0-9]{4}'

    @property
    def state(self):
        """Return the state of the device."""
        return STATE_UNKNOWN

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        raise NotImplementedError()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        raise NotImplementedError()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        raise NotImplementedError()

    def alarm_trigger(self, code=None):
        """Alarm trigger command."""
        raise NotImplementedError()
