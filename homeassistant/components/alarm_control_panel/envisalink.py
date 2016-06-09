"""
Support for Envisalink-based alarm control panels (Honeywell/DSC).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.envisalink/
"""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.envisalink import (EVL_CONTROLLER,
                                                 EnvisalinkDevice,
                                                 SIGNAL_PARTITION_UPDATE,
                                                 SIGNAL_KEYPAD_UPDATE)
from homeassistant.util import convert
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN, STATE_ALARM_TRIGGERED)

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Envisalink alarm panels."""
    _configuredPartitions = discovery_info['partitions']
    _code = discovery_info['code']
    add_devices_callback(EnvisalinkAlarm(partNum,
                                         convert(_configuredPartitions[partNum]['name'],
                                                 str,
                                                 str.format("Partition #{0}", partNum)),
                                         _code,
                                         EVL_CONTROLLER.alarm_state['partition'][partNum], 
                                         EVL_CONTROLLER)
                         for partNum in _configuredPartitions)
    return True

class EnvisalinkAlarm(EnvisalinkDevice, alarm.AlarmControlPanel):
    """Represents the Envisalink-based alarm panel."""

    def __init__(self, partitionNumber, alarmName, code, info, controller):
        """Initialize the alarm panel."""
        from pydispatch import dispatcher
        self._partitionNumber = partitionNumber
        self._code = code
        _LOGGER.info('Setting up alarm: ' + alarmName)
        EnvisalinkDevice.__init__(self, alarmName, info, controller)
        dispatcher.connect(self._update_callback,
                           signal=SIGNAL_PARTITION_UPDATE,
                           sender=dispatcher.Any)
        dispatcher.connect(self._update_callback,
                           signal=SIGNAL_KEYPAD_UPDATE,
                           sender=dispatcher.Any)

    def _update_callback(self):
        self.update_ha_state()

    @property
    def code_format(self):
        """The characters if code is defined."""
        return self._code

    @property
    def state(self):
        """Return the state of the device."""
        if self._info['status']['alarm']:
            return STATE_ALARM_TRIGGERED
        elif self._info['status']['armed_away']:
            return STATE_ALARM_ARMED_AWAY
        elif self._info['status']['armed_stay']:
            return STATE_ALARM_ARMED_HOME
        elif self._info['status']['alpha']:
            return STATE_ALARM_DISARMED
        else:
            return STATE_UNKNOWN

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if self._code:
            EVL_CONTROLLER.disarm_partition(str(code), self._partitionNumber)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if self._code:
            EVL_CONTROLLER.arm_stay_partition(str(code), self._partitionNumber)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._code:
            EVL_CONTROLLER.arm_away_partition(str(code), self._partitionNumber)

    def alarm_trigger(self, code=None):
        """Alarm trigger command. Not possible for us."""
        raise NotImplementedError()
