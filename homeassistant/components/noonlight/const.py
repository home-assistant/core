"""Constants for the Noonlight integration."""
from homeassistant.const import CONF_MODE
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


ATTR_NOONLIGHT_ALARM_ID = "noonlight_alarm_id"
