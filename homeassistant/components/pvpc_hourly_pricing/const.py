"""Constant values for pvpc_hourly_pricing."""
from aiopvpc import TARIFFS

DOMAIN = "pvpc_hourly_pricing"
PLATFORMS = ["sensor"]
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC"
DEFAULT_TARIFF = TARIFFS[1]
