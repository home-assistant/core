"""
Demo platform that has two fake alarm control panels.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import homeassistant.components.alarm_control_panel.manual as manual


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo alarm control panel platform."""
    add_devices([
        manual.ManualAlarm(hass, 'Alarm', '1234', 5, 10, False),
    ])
