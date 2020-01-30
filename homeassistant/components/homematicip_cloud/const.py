"""Constants for the HomematicIP Cloud component."""
import logging

_LOGGER = logging.getLogger(".")

DOMAIN = "homematicip_cloud"

COMPONENTS = [
    "alarm_control_panel",
    "binary_sensor",
    "climate",
    "cover",
    "light",
    "sensor",
    "switch",
    "weather",
]

CONF_ACCESSPOINT = "accesspoint"
CONF_AUTHTOKEN = "authtoken"

HMIPC_NAME = "name"
HMIPC_HAPID = "hapid"
HMIPC_AUTHTOKEN = "authtoken"
HMIPC_PIN = "pin"
