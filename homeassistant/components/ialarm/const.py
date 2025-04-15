"""Constants for the iAlarm integration."""

from pyialarm import IAlarm

from homeassistant.components.alarm_control_panel import AlarmControlPanelState

DATA_COORDINATOR = "ialarm"

DEFAULT_PORT = 18034

DOMAIN = "ialarm"

IALARM_TO_HASS = {
    IAlarm.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    IAlarm.ARMED_STAY: AlarmControlPanelState.ARMED_HOME,
    IAlarm.DISARMED: AlarmControlPanelState.DISARMED,
    IAlarm.TRIGGERED: AlarmControlPanelState.TRIGGERED,
}
