"""Demo platform that has two fake alarm control panels."""
import datetime
from homeassistant.components.manual.alarm_control_panel import ManualAlarm
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED, CONF_DELAY_TIME,
    CONF_PENDING_TIME, CONF_TRIGGER_TIME)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Demo alarm control panel platform."""
    async_add_entities([
        ManualAlarm(hass, 'Alarm', '1234', None, False, {
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
