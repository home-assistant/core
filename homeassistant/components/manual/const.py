"""Constants for Manual alarm control panel."""
from datetime import timedelta

CONF_CODE_TEMPLATE = "code_template"
CONF_CODE_ARM_REQUIRED = "code_arm_required"

ATTR_PREVIOUS_STATE = "previous_state"
ATTR_NEXT_STATE = "next_state"

DEFAULT_ALARM_NAME = "HA Alarm"
DEFAULT_DELAY_TIME = timedelta(seconds=60)
DEFAULT_ARMING_TIME = timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False
