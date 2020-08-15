"""Constants for the Elexa Guardian integration."""
import logging

DOMAIN = "guardian"

LOGGER = logging.getLogger(__package__)

CONF_UID = "uid"

DATA_CLIENT = "client"
DATA_DIAGNOSTICS = "diagnostics"
DATA_PAIR_DUMP = "pair_sensor"
DATA_PING = "ping"
DATA_SENSOR_STATUS = "sensor_status"
DATA_VALVE_STATUS = "valve_status"
DATA_WIFI_STATUS = "wifi_status"

SENSOR_KIND_AP_INFO = "ap_enabled"
SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_UPTIME = "uptime"

SWITCH_KIND_VALVE = "valve"

TOPIC_UPDATE = "guardian_update_{0}"
