"""
Support for Envisalink-based alarm control panels (Honeywell/DSC).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.envisalink/
"""
import logging
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.envisalink import (EVL_CONTROLLER,
                                                 EnvisalinkDevice,
                                                 PARTITION_SCHEMA,
                                                 CONF_CODE,
                                                 CONF_PANIC,
                                                 CONF_PARTITIONNAME,
                                                 SIGNAL_PARTITION_UPDATE,
                                                 SIGNAL_KEYPAD_UPDATE)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN, STATE_ALARM_TRIGGERED)

DEPENDENCIES = ['envisalink']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Envisalink alarm panels."""
    _configured_partitions = discovery_info['partitions']
    _code = discovery_info[CONF_CODE]
    _panic_type = discovery_info[CONF_PANIC]
    for part_num in _configured_partitions:
        _device_config_data = PARTITION_SCHEMA(
            _configured_partitions[part_num])
        _device = EnvisalinkAlarm(
            part_num,
            _device_config_data[CONF_PARTITIONNAME],
            _code,
            _panic_type,
            EVL_CONTROLLER.alarm_state['partition'][part_num],
            EVL_CONTROLLER)
        add_devices_callback([_device])

    return True


class EnvisalinkAlarm(EnvisalinkDevice, alarm.AlarmControlPanel):
    """Represents the Envisalink-based alarm panel."""

    # pylint: disable=too-many-arguments
    def __init__(self, partition_number, alarm_name,
                 code, panic_type, info, controller):
        """Initialize the alarm panel."""
        from pydispatch import dispatcher
        self._partition_number = partition_number
        self._code = code
        self._panic_type = panic_type
        _LOGGER.debug('Setting up alarm: ' + alarm_name)
        EnvisalinkDevice.__init__(self, alarm_name, info, controller)
        dispatcher.connect(self._update_callback,
                           signal=SIGNAL_PARTITION_UPDATE,
                           sender=dispatcher.Any)
        dispatcher.connect(self._update_callback,
                           signal=SIGNAL_KEYPAD_UPDATE,
                           sender=dispatcher.Any)

    def _update_callback(self, partition):
        """Update HA state, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.hass.async_add_job(self.update_ha_state)

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
            EVL_CONTROLLER.disarm_partition(str(code),
                                            self._partition_number)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if self._code:
            EVL_CONTROLLER.arm_stay_partition(str(code),
                                              self._partition_number)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._code:
            EVL_CONTROLLER.arm_away_partition(str(code),
                                              self._partition_number)

    def alarm_trigger(self, code=None):
        """Alarm trigger command. Will be used to trigger a panic alarm."""
        if self._code:
            EVL_CONTROLLER.panic_alarm(self._panic_type)
