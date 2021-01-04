"""Constants for the Shelly integration."""

COAP = "coap"
DATA_CONFIG_ENTRY = "config_entry"
DOMAIN = "shelly"
REST = "rest"

# Used to calculate the timeout in "_async_update_data" used for polling data from devices.
POLLING_TIMEOUT_MULTIPLIER = 1.2

# Refresh interval for REST sensors
REST_SENSORS_UPDATE_INTERVAL = 60

# Timeout used for aioshelly calls
AIOSHELLY_DEVICE_TIMEOUT_SEC = 10

# Multiplier used to calculate the "update_interval" for sleeping devices.
SLEEP_PERIOD_MULTIPLIER = 1.2

# Multiplier used to calculate the "update_interval" for non-sleeping devices.
UPDATE_PERIOD_MULTIPLIER = 2.2

# Shelly Air - Maximum work hours before lamp replacement
SHAIR_MAX_WORK_HOURS = 9000

# Map Shelly input events
INPUTS_EVENTS_DICT = {
    "S": "single",
    "SS": "double",
    "SSS": "triple",
    "L": "long",
    "SL": "single_long",
    "LS": "long_single",
}

# List of battery devices that maintain a permanent WiFi connection
BATTERY_DEVICES_WITH_PERMANENT_CONNECTION = ["SHMOS-01"]
