"""Constants for the Risco integration."""

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import CONF_SCAN_INTERVAL

DOMAIN = "risco"

RISCO_EVENT = "risco_event"

DATA_COORDINATOR = "risco"
EVENTS_COORDINATOR = "risco_events"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_CONCURRENCY = 4

TYPE_LOCAL = "local"

MAX_COMMUNICATION_DELAY = 3

SYSTEM_UPDATE_SIGNAL = "risco_system_update"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_DISARM_REQUIRED = "code_disarm_required"
CONF_RISCO_STATES_TO_HA = "risco_states_to_ha"
CONF_HA_STATES_TO_RISCO = "ha_states_to_risco"
CONF_COMMUNICATION_DELAY = "communication_delay"
CONF_CONCURRENCY = "concurrency"

RISCO_GROUPS = ["A", "B", "C", "D"]
RISCO_ARM = "arm"
RISCO_PARTIAL_ARM = "partial_arm"
RISCO_STATES = [RISCO_ARM, RISCO_PARTIAL_ARM, *RISCO_GROUPS]

DEFAULT_RISCO_GROUPS_TO_HA = dict.fromkeys(
    RISCO_GROUPS, AlarmControlPanelState.ARMED_HOME
)
DEFAULT_RISCO_STATES_TO_HA = {
    RISCO_ARM: AlarmControlPanelState.ARMED_AWAY,
    RISCO_PARTIAL_ARM: AlarmControlPanelState.ARMED_HOME,
    **DEFAULT_RISCO_GROUPS_TO_HA,
}

DEFAULT_HA_STATES_TO_RISCO = {
    AlarmControlPanelState.ARMED_AWAY: RISCO_ARM,
    AlarmControlPanelState.ARMED_HOME: RISCO_PARTIAL_ARM,
}

DEFAULT_OPTIONS = {
    CONF_CODE_ARM_REQUIRED: False,
    CONF_CODE_DISARM_REQUIRED: False,
    CONF_RISCO_STATES_TO_HA: DEFAULT_RISCO_STATES_TO_HA,
    CONF_HA_STATES_TO_RISCO: DEFAULT_HA_STATES_TO_RISCO,
}

DEFAULT_ADVANCED_OPTIONS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_CONCURRENCY: DEFAULT_CONCURRENCY,
}
