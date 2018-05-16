"""
Demo platform that has two fake alarm control panels.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import datetime
import homeassistant.components.alarm_control_panel.manual as manual
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED, CONF_DELAY_TIME,
    CONF_PENDING_TIME, CONF_TRIGGER_TIME)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo alarm control panel platform."""
    add_devices([
        manual.ManualAlarm(hass, 'Alarm', '1234', None, False, {
            STATE_ALARM_ARMED_AWAY: {
                CONF_DELAY_TIME: datetime.timedelta(seconds=0),
                CONF_PENDING_TIME: datetime.timedelta(seconds=5),
                CONF_TRIGGER_TIME: datetime.timedelta(seconds=10),
            },
            STATE_ALARM_ARMED_HOME: {
                CONF_DELAY_TIME: datetime.timedelta(seconds=0),
                CONF_PENDING_TIME: datetime.timedelta(seconds=5),
                CONF_TRIGGER_TIME: datetime.timedelta(seconds=10),
            },
            STATE_ALARM_ARMED_NIGHT: {
                CONF_DELAY_TIME: datetime.timedelta(seconds=0),
                CONF_PENDING_TIME: datetime.timedelta(seconds=5),
                CONF_TRIGGER_TIME: datetime.timedelta(seconds=10),
            },
            STATE_ALARM_DISARMED: {
                CONF_DELAY_TIME: datetime.timedelta(seconds=0),
                CONF_TRIGGER_TIME: datetime.timedelta(seconds=10),
            },
            STATE_ALARM_ARMED_CUSTOM_BYPASS: {
                CONF_DELAY_TIME: datetime.timedelta(seconds=0),
                CONF_PENDING_TIME: datetime.timedelta(seconds=5),
                CONF_TRIGGER_TIME: datetime.timedelta(seconds=10),
            },
            STATE_ALARM_TRIGGERED: {
                CONF_PENDING_TIME: datetime.timedelta(seconds=5),
            },
        }),
    ])
