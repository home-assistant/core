"""Constants for the iAlarm integration."""
from pyialarm import IAlarm

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

DATA_COORDINATOR = "ialarm"

DEFAULT_PORT = 18034

DOMAIN = "ialarm"

IALARM_TO_HASS = {
    IAlarm.ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    IAlarm.ARMED_STAY: STATE_ALARM_ARMED_HOME,
    IAlarm.DISARMED: STATE_ALARM_DISARMED,
    IAlarm.TRIGGERED: STATE_ALARM_TRIGGERED,
}
