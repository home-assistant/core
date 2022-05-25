"""Constants for the iAlarmXR integration."""
from pyialarmxr import IAlarmXR

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

DOMAIN = "ialarm_xr"

IALARMXR_TO_HASS = {
    IAlarmXR.ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    IAlarmXR.ARMED_STAY: STATE_ALARM_ARMED_HOME,
    IAlarmXR.DISARMED: STATE_ALARM_DISARMED,
    IAlarmXR.TRIGGERED: STATE_ALARM_TRIGGERED,
}
