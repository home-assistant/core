"""Constants for the iAlarm integration."""

from pyialarm import IAlarm

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityState

DATA_COORDINATOR = "ialarm"

DEFAULT_PORT = 18034

DOMAIN = "ialarm"

IALARM_TO_HASS = {
    IAlarm.ARMED_AWAY: AlarmControlPanelEntityState.ARMED_AWAY,
    IAlarm.ARMED_STAY: AlarmControlPanelEntityState.ARMED_HOME,
    IAlarm.DISARMED: AlarmControlPanelEntityState.DISARMED,
    IAlarm.TRIGGERED: AlarmControlPanelEntityState.TRIGGERED,
}
