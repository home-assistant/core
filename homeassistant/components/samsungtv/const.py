"""Constants for the Samsung TV integration."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "samsungtv"

DEFAULT_NAME = "Samsung TV"

VALUE_CONF_NAME = "HomeAssistant"
VALUE_CONF_ID = "ha.component.samsung"

CONF_DESCRIPTION = "description"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_ON_ACTION = "turn_on_action"

RESULT_AUTH_MISSING = "auth_missing"
RESULT_SUCCESS = "success"
RESULT_CANNOT_CONNECT = "cannot_connect"
RESULT_NOT_SUPPORTED = "not_supported"

METHOD_LEGACY = "legacy"
METHOD_WEBSOCKET = "websocket"
