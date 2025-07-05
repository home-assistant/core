"""Constants for the Eway integration."""

from __future__ import annotations

from typing import Final

# Domain
DOMAIN: Final = "eway"

# Default values
DEFAULT_NAME = "Eway Inverter"
DEFAULT_SCAN_INTERVAL = 30

# Configuration keys
CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_SN = "device_sn"
CONF_KEEPALIVE = "keepalive"
CONF_DEVICE_MODEL = "device_model"
CONF_SCAN_INTERVAL = "scan_interval"

# MQTT topics
MQTT_TOPIC_PREFIX = "eway"
MQTT_TOPIC_STATUS = "status"
MQTT_TOPIC_DATA = "data"

# Device attributes
ATTR_GEN_POWER = "gen_power"
ATTR_GRID_VOLTAGE = "grid_voltage"
ATTR_INPUT_CURRENT = "input_current"
ATTR_GRID_FREQ = "grid_freq"
ATTR_TEMPERATURE = "temperature"
ATTR_GEN_POWER_TODAY = "gen_power_today"
ATTR_GEN_POWER_TOTAL = "gen_power_total"
ATTR_INPUT_VOLTAGE = "input_voltage"
ATTR_ERROR_CODE = "error_code"
ATTR_DURATION = "duration"
