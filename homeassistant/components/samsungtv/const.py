"""Constants for the Samsung TV integration."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "samsungtv"

ATTR_PROPERTIES = "properties"

DEFAULT_NAME = "Samsung TV"

VALUE_CONF_NAME = "HomeAssistant"
VALUE_CONF_ID = "ha.component.samsung"

CONF_DESCRIPTION = "description"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_ON_ACTION = "turn_on_action"
CONF_SERIALNO = "serial_number"

RESULT_AUTH_MISSING = "auth_missing"
RESULT_SUCCESS = "success"
RESULT_NOT_SUCCESSFUL = "cannot_connect"
RESULT_NOT_SUPPORTED = "not_supported"
RESULT_UNKNOWN_HOST = "unknown"

METHOD_LEGACY = "legacy"
METHOD_WEBSOCKET = "websocket"

WEBSOCKET_PORTS = (8002, 8001)

# Soundbar models: "HW-Q60R", "HW-Q70R", "HW-Q90R", "HW-Q60T", "HW-Q70T", "HW-Q90T"
MODEL_SOUNDBAR = "HW-Q"
