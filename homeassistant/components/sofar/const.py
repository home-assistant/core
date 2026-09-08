"""Constants for the Sofar integration."""

DOMAIN = "sofar"
ATTR_MANUFACTURER = "Sofar Solar"

DEFAULT_NAME = "Sofar"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
SCAN_INTERVAL = 5
SETTINGS_SCAN_INTERVAL = 60

CONF_UNIT_ID = "unit_id"

BATTERY_COMPONENTS = {
    n: "battery_1_2" if n <= 2 else "battery_3_8" for n in range(1, 9)
}
