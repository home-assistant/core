"""Constants for the Noonlight integration."""

import logging

DOMAIN = "noonlight"
_LOGGER = logging.getLogger(__package__)
DATA_NOONLIGHT_CONFIG = "noonlight_config"
CONF_CITY = "city"
CONF_STATE = "state"
CONF_ZIPCODE = "zip_code"
CONF_SERVICES = "services"
CONF_SERVICES_LIST = ["Police", "Fire", "Medical", "Other"]
CONF_INSTRUCTIONS = "instructions"
CONF_PHONE = "phone"
CONF_ADDRESS_NAME = "name"
CONF_MODE_LIST = ["Sandbox", "Production"]
CONF_MODE_PRODUCTION = "Production"
CONF_MODE_SANDBOX = "Sandbox"

ATTR_NOONLIGHT_ALARM_ID = "noonlight_alarm_id"
