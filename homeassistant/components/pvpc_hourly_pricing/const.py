"""Constant values for pvpc_hourly_pricing."""
from homeassistant.const import Platform

DOMAIN = "pvpc_hourly_pricing"
PLATFORMS = [Platform.SENSOR]
ATTR_POWER = "power"
ATTR_POWER_P3 = "power_p3"
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC"
