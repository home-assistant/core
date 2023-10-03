"""Constants for the EnergyZero integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

import voluptuous as vol

DOMAIN: Final = "energyzero"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)
THRESHOLD_HOUR: Final = 14

ATTR_TYPE: Final = "type"
ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_INCL_VAT: Final = "incl_vat"

SERVICE_TYPE_DEVICE_NAMES = {
    "today_energy": "Energy market price",
    "today_gas": "Gas market price",
}
SERVICE_NAME: Final = "get_prices"
SERVICE_PRICE_TYPES: Final = ["energy", "gas"]
SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_TYPE): vol.In(SERVICE_PRICE_TYPES),
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
        vol.Optional(ATTR_INCL_VAT, default=True): bool,
    }
)
