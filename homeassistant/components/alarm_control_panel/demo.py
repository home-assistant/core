"""
Demo platform that has two fake alarm control panels.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import homeassistant.components.alarm_control_panel.manual as manual
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_TRIGGERED, CONF_PENDING_TIME)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo alarm control panel platform."""
    add_devices([
        manual.ManualAlarm(hass, 'Alarm', '1234', 5, 10, False, {
            STATE_ALARM_ARMED_AWAY: {
                CONF_PENDING_TIME: 5
            },
            STATE_ALARM_ARMED_HOME: {
                CONF_PENDING_TIME: 5
            },
            STATE_ALARM_ARMED_NIGHT: {
                CONF_PENDING_TIME: 5
            },
            STATE_ALARM_TRIGGERED: {
                CONF_PENDING_TIME: 5
            },
        }),
    ])
