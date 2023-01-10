"""Const file for the MyBMW integration."""
from homeassistant.const import UnitOfLength, UnitOfVolume

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
    "KILOMETERS": UnitOfLength.KILOMETERS,
    "MILES": UnitOfLength.MILES,
    "LITERS": UnitOfVolume.LITERS,
    "GALLONS": UnitOfVolume.GALLONS,
}
