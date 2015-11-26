"""
homeassistant.components.alarm_control_panel.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that has two fake alarm control panels.
"""
import homeassistant.components.alarm_control_panel.manual as Alarm
from homeassistant.const import (STATE_ALARM_DISARMED,
                                 STATE_ALARM_ARMED_AWAY)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo alarm control panels. """
    add_devices([

        DemoAlarmControlPanel(hass, 'Front door', '1234', 2, 4,
                              STATE_ALARM_DISARMED),
        DemoAlarmControlPanel(hass, 'Safe', '1234', 2, 4,
                              STATE_ALARM_ARMED_AWAY),
        ])


# pylint: disable=too-many-arguments
class DemoAlarmControlPanel(Alarm.ManualAlarm):
    """ A Demo alarm control panel. """

    def __init__(self, hass, name, code, pending_time, trigger_time, state):
        super().__init__(hass, name, code, pending_time, trigger_time)
        self._state = state

    @property
    def should_poll(self):
        """ No polling needed for a demo panel. """
        return False

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state
