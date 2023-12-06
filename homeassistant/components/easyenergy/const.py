"""Constants for the easyEnergy integration."""
from __future__ import annotations

from datetime import timedelta
from enum import Enum
import logging
from typing import Final

import voluptuous as vol

DOMAIN: Final = "easyenergy"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)
THRESHOLD_HOUR: Final = 14

ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_INCL_VAT: Final = "incl_vat"

SERVICE_TYPE_DEVICE_NAMES = {
    "today_energy_usage": "Energy market price - Usage",
    "today_energy_return": "Energy market price - Return",
    "today_gas": "Gas market price",
}

GAS_SERVICE_NAME: Final = "get_gas_prices"
ENERGY_USAGE_SERVICE_NAME: Final = "get_energy_usage_prices"
ENERGY_RETURN_SERVICE_NAME: Final = "get_energy_return_prices"
SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
        vol.Optional(ATTR_INCL_VAT, default=True): bool,
    }
)


class PriceType(str, Enum):
    """Type of price."""

    ENERGY_USAGE = "energy_usage"
    ENERGY_RETURN = "energy_return"
    GAS = "gas"
