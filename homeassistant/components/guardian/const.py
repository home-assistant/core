"""Constants for the Elexa Guardian integration."""
import logging

DOMAIN = "guardian"

LOGGER = logging.getLogger(__package__)

API_SENSOR_PAIRED_SENSOR_STATUS = "sensor_paired_sensor_status"
API_SENSOR_PAIR_DUMP = "sensor_pair_dump"
API_SYSTEM_DIAGNOSTICS = "system_diagnostics"
API_SYSTEM_ONBOARD_SENSOR_STATUS = "system_onboard_sensor_status"
API_VALVE_STATUS = "valve_status"
API_WIFI_STATUS = "wifi_status"

CONF_UID = "uid"

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
DATA_PAIRED_SENSOR_MANAGER = "paired_sensor_manager"
DATA_UNSUB_DISPATCHER_CONNECT = "unsub_dispatcher_connect"

SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED = "guardian_paired_sensor_coordinator_added_{0}"
