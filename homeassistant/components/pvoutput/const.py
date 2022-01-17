"""Constants for the PVOutput integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "pvoutput"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=2)


ATTR_ENERGY_GENERATION = "energy_generation"
ATTR_POWER_GENERATION = "power_generation"
ATTR_ENERGY_CONSUMPTION = "energy_consumption"
ATTR_POWER_CONSUMPTION = "power_consumption"
ATTR_EFFICIENCY = "efficiency"

CONF_SYSTEM_ID = "system_id"

DEFAULT_NAME = "PVOutput"
