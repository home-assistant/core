"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""

from elkm1_lib.const import Max

DOMAIN = "elkm1"

CONF_AUTO_CONFIGURE = "auto_configure"
CONF_AREA = "area"
CONF_COUNTER = "counter"
CONF_ENABLED = "enabled"
CONF_KEYPAD = "keypad"
CONF_OUTPUT = "output"
CONF_PLC = "plc"
CONF_SETTING = "setting"
CONF_TASK = "task"
CONF_THERMOSTAT = "thermostat"
CONF_ZONE = "zone"
CONF_PREFIX = "prefix"


BARE_TEMP_FAHRENHEIT = "F"
BARE_TEMP_CELSIUS = "C"

ELK_ELEMENTS = {
    CONF_AREA: Max.AREAS.value,
    CONF_COUNTER: Max.COUNTERS.value,
    CONF_KEYPAD: Max.KEYPADS.value,
    CONF_OUTPUT: Max.OUTPUTS.value,
    CONF_PLC: Max.LIGHTS.value,
    CONF_SETTING: Max.SETTINGS.value,
    CONF_TASK: Max.TASKS.value,
    CONF_THERMOSTAT: Max.THERMOSTATS.value,
    CONF_ZONE: Max.ZONES.value,
}


ATTR_CHANGED_BY_KEYPAD = "changed_by_keypad"
ATTR_CHANGED_BY_ID = "changed_by_id"
ATTR_CHANGED_BY_TIME = "changed_by_time"
