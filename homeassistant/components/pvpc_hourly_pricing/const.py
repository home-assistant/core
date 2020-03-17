"""Constant values for pvpc_hourly_pricing."""
from aiopvpc import DEFAULT_TIMEOUT, TARIFFS  # noqa: F401

DOMAIN = "pvpc_hourly_pricing"
PLATFORM = "sensor"
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC"

DEFAULT_TARIFF = TARIFFS[1]
