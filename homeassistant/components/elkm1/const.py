"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""

from datetime import timedelta

from elkm1_lib.const import Max
import voluptuous as vol

from homeassistant.const import ATTR_CODE, CONF_ZONE

DOMAIN = "elkm1"

LOGIN_TIMEOUT = 20

CONF_AUTO_CONFIGURE = "auto_configure"
CONF_AREA = "area"
CONF_COUNTER = "counter"
CONF_KEYPAD = "keypad"
CONF_OUTPUT = "output"
CONF_PLC = "plc"
CONF_SETTING = "setting"
CONF_TASK = "task"
CONF_THERMOSTAT = "thermostat"

DISCOVER_SCAN_TIMEOUT = 10
DISCOVERY_INTERVAL = timedelta(minutes=15)

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

EVENT_ELKM1_KEYPAD_KEY_PRESSED = "elkm1.keypad_key_pressed"


ATTR_KEYPAD_ID = "keypad_id"
ATTR_KEY = "key"
ATTR_KEY_NAME = "key_name"
ATTR_KEYPAD_NAME = "keypad_name"
ATTR_CHANGED_BY_KEYPAD = "changed_by_keypad"
ATTR_CHANGED_BY_ID = "changed_by_id"
ATTR_CHANGED_BY_TIME = "changed_by_time"
ATTR_VALUE = "value"

ELK_USER_CODE_SERVICE_SCHEMA = {
    vol.Required(ATTR_CODE): vol.All(vol.Coerce(int), vol.Range(0, 999999))
}
