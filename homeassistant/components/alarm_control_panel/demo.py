"""
homeassistant.components.alarm_control_panel.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that has two fake alarm control panels.
"""
import homeassistant.components.alarm_control_panel as Alarm
from homeassistant.const import (STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
                                 STATE_ALARM_ARMED_AWAY)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo alarm control panels. """
    add_devices([
        DemoAlarmControlPanel('Front door', '1234', STATE_ALARM_ARMED_HOME),
        DemoAlarmControlPanel('Safe', '1234', STATE_ALARM_ARMED_AWAY),
        ])


class DemoAlarmControlPanel(Alarm.AlarmControlPanel):
    """ A Demo alarm control panel. """

    def __init__(self, name, code, state):
        self._state = state
        self._name = name
        self._code = str(code) if code else None

    @property
    def should_poll(self):
        """ No polling needed. """
        return False

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def code_format(self):
        """ One or more characters. """
        return None if self._code is None else '.+'

    def alarm_disarm(self, code=None):
        """ Send disarm command. """
        if not self._validate_code(code, STATE_ALARM_DISARMED):
            return
        self._state = STATE_ALARM_DISARMED
        self.update_ha_state()

    def alarm_arm_home(self, code=None):
        """ Send arm home command. """
        if not self._validate_code(code, STATE_ALARM_ARMED_HOME):
            return
        self._state = STATE_ALARM_ARMED_HOME
        self.update_ha_state()

    def alarm_arm_away(self, code=None):
        """ Send arm away command. """
        if not self._validate_code(code, STATE_ALARM_ARMED_AWAY):
            return
        self._state = STATE_ALARM_ARMED_AWAY
        self.update_ha_state()

    def alarm_trigger(self, code=None):
        """ Send alarm trigger command. No code needed. """
        pass

    def _validate_code(self, code, state):
        """ Validate given code. """
        return self._code is None or code == self._code
