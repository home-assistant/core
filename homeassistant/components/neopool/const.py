"""Constants for the NeoPool integration."""

from homeassistant.const import Platform

DOMAIN = "neopool"
NAME = "NeoPool"

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

DEFAULT_SCAN_INTERVAL = 20  # in seconds
FOLLOW_UP_REFRESH_DELAY = 2.0  # seconds  (delay before a 2nd refresh for IO entity)
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

CONF_UNIT_ID = "unit_id"
CONF_MODBUS_FRAMER = "modbus_framer"

CONF_USE_LIGHT = "use_light"
CONF_USE_COVER_SENSOR = "use_cover_sensor"
CONF_USE_AUX1 = "use_aux1"
CONF_USE_AUX2 = "use_aux2"
CONF_USE_AUX3 = "use_aux3"
CONF_USE_AUX4 = "use_aux4"

CURRENT_VERSION = 6
