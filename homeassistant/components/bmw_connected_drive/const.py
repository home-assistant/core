"""Const file for the MyBMW integration."""
from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)

DOMAIN = "bmw_connected_drive"
ATTRIBUTION = "Data provided by MyBMW"

ATTR_DIRECTION = "direction"
ATTR_VIN = "vin"

CONF_ALLOWED_REGIONS = ["china", "north_america", "rest_of_world"]
CONF_READ_ONLY = "read_only"
CONF_ACCOUNT = "account"
CONF_REFRESH_TOKEN = "refresh_token"

DATA_HASS_CONFIG = "hass_config"

UNIT_MAP = {
    "KILOMETERS": LENGTH_KILOMETERS,
    "MILES": LENGTH_MILES,
    "LITERS": VOLUME_LITERS,
    "GALLONS": VOLUME_GALLONS,
}
