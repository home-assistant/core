"""
homeassistant.components.alarm_control_panel.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that has two fake alarm control panels.
"""
import homeassistant.components.alarm_control_panel.manual as manual


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo alarm control panels. """
    add_devices([
        manual.ManualAlarm(hass, 'Alarm', '1234', 5, 10),
    ])
