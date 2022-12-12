"""Constants for the EnergyZero integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "energyzero"
ATTRIBUTION: Final = "Data provided by EnergyZero"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)

CONF_GAS: Final = "gas"

SERVICE_ENERGY_TODAY: Final = "energy_today"
SERVICE_ENERGY_TOMORROW: Final = "energy_tomorrow"
SERVICE_GAS_TODAY: Final = "gas_today"
SERVICE_GAS_TOMORROW: Final = "gas_tomorrow"

THRESHOLD_HOUR: Final = 14
