"""Constants for the EnergyZero integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "energyzero"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)
THRESHOLD_HOUR: Final = 14

SERVICE_TYPE_DEVICE_NAMES = {
    "today_energy": "Energy market price",
    "today_gas": "Gas market price",
}

CONF_GAS_MODIFYER = "gas_modifyer"
CONF_ENERGY_MODIFYER = "energy_modifyer"

DEFAULT_MODIFYER = '{% set s = {"BTW": 1.21 } %}{{ price * s.BTW | float | round(5)}}'
