"""Constants for the Elexa Guardian integration."""
import logging

DOMAIN = "guardian"

LOGGER = logging.getLogger(__package__)

DATA_CLIENT = "client"
DATA_DIAGNOSTICS = "diagnostics"
DATA_PAIR_DUMP = "pair_sensor"
DATA_PING = "ping"
DATA_SENSOR_STATUS = "sensor_status"
DATA_VALVE_STATUS = "valve_status"
DATA_WIFI_STATUS = "wifi_status"

TOPIC_UPDATE = "guardian_update_{0}"
