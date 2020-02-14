"""Constants for the Samsung TV integration."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "samsungtv"

DEFAULT_NAME = "Samsung TV"

CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_ON_ACTION = "turn_on_action"
CONF_TOKEN = "token"

RESULT_AUTH_MISSING = "auth_missing"
RESULT_SUCCESS = "success"
RESULT_NOT_SUCCESSFUL = "not_successful"
RESULT_NOT_SUPPORTED = "not_supported"
