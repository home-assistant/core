"""Constants for the Elexa Guardian integration."""
import logging

DOMAIN = "guardian"

LOGGER = logging.getLogger(__package__)

CONF_UID = "uid"

API_SENSOR_PAIR_DUMP = "sensor_pair_dump"
API_SYSTEM_DIAGNOSTICS = "system_diagnostics"
API_SYSTEM_ONBOARD_SENSOR_STATUS = "system_onboard_sensor_status"
API_VALVE_STATUS = "valve_status"

DATA_CLIENT = "client"
# DATA_VALVE_STATUS = "valve_status"
# DATA_WIFI_STATUS = "wifi_status"

SENSOR_KIND_AP_INFO = "ap_enabled"
SENSOR_KIND_LEAK_DETECTED = "leak_detected"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_UPTIME = "uptime"

SWITCH_KIND_VALVE = "valve"

TOPIC_UPDATE = "guardian_update_{0}"
