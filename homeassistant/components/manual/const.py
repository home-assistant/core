"""Constants for the manual integration."""

import datetime as dt
from enum import StrEnum

from homeassistant.components.alarm_control_panel import AlarmControlPanelState

DOMAIN = "manual"

CONF_ARMING_STATES = "arming_states"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_TEMPLATE = "code_template"

DEFAULT_ALARM_NAME = "HA Alarm"
DEFAULT_DELAY_TIME = dt.timedelta(seconds=60)
DEFAULT_ARMING_TIME = dt.timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = dt.timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False

SUPPORTED_ARMING_STATES = [
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_HOME,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_VACATION,
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
]


class ManualEntityStateAttribute(StrEnum):
    """State attributes for manual alarm control panel entities."""

    NEXT_STATE = "next_state"
    PREVIOUS_STATE = "previous_state"
