"""Constants for Manual alarm component."""

import datetime

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    Platform,
)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL]

DOMAIN = "manual"

CONF_ARMING_STATES = "arming_states"
CONF_CODE_TEMPLATE = "code_template"
CONF_CODE_ARM_REQUIRED = "code_arm_required"

DEFAULT_ALARM_NAME = "HA Alarm"
DEFAULT_DELAY_TIME = datetime.timedelta(seconds=60)
DEFAULT_ARMING_TIME = datetime.timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = datetime.timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False

SUPPORTED_STATES = [
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_TRIGGERED,
]

SUPPORTED_PRETRIGGER_STATES = [
    state for state in SUPPORTED_STATES if state != STATE_ALARM_TRIGGERED
]

SUPPORTED_ARMING_STATES = [
    state
    for state in SUPPORTED_STATES
    if state not in (STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED)
]

SUPPORTED_ARMING_STATE_TO_FEATURE = {
    STATE_ALARM_ARMED_AWAY: AlarmControlPanelEntityFeature.ARM_AWAY,
    STATE_ALARM_ARMED_HOME: AlarmControlPanelEntityFeature.ARM_HOME,
    STATE_ALARM_ARMED_NIGHT: AlarmControlPanelEntityFeature.ARM_NIGHT,
    STATE_ALARM_ARMED_VACATION: AlarmControlPanelEntityFeature.ARM_VACATION,
    STATE_ALARM_ARMED_CUSTOM_BYPASS: AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
}
