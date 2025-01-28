# const.py
"""Constants for the B-Route Smart Meter integration."""

DOMAIN = "b_route_meter"

# Configuration
CONF_ROUTE_B_ID = "route_b_id"
CONF_ROUTE_B_PWD = "route_b_pwd"
CONF_SERIAL_PORT = "serial_port"
CONF_RETRY_COUNT = "retry_count"

# Defaults
DEFAULT_RETRY_COUNT = 3
DEFAULT_SERIAL_PORT = "/dev/ttyS0"
DEFAULT_UPDATE_INTERVAL = 10  # seconds

# Device Info
DEVICE_MANUFACTURER = "ROHM Co., Ltd."
DEVICE_MODEL = "BP35A1"
DEVICE_NAME = "B-Route Smart Meter"

# Unique IDs
DEVICE_UNIQUE_ID = "b_route_meter_device"
