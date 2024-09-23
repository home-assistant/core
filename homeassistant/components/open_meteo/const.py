"""Constants for the Open-Meteo integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
)

DOMAIN: Final = "open_meteo"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=30)

# World Meteorological Organization Weather Code
# mapped to Home Assistant weather conditions.
# https://www.weather.gov/tg/wmo
WMO_TO_HA_CONDITION_MAP = {
    0: ATTR_CONDITION_SUNNY,  # Clear sky
    1: ATTR_CONDITION_SUNNY,  # Mainly clear
    2: ATTR_CONDITION_PARTLYCLOUDY,  # Partly cloudy
    3: ATTR_CONDITION_CLOUDY,  # Overcast
    45: ATTR_CONDITION_FOG,  # Fog
    48: ATTR_CONDITION_FOG,  # Depositing rime fog  # codespell:ignore rime
    51: ATTR_CONDITION_RAINY,  # Drizzle: Light intensity
    53: ATTR_CONDITION_RAINY,  # Drizzle: Moderate intensity
    55: ATTR_CONDITION_RAINY,  # Drizzle: Dense intensity
    56: ATTR_CONDITION_RAINY,  # Freezing Drizzle: Light intensity
    57: ATTR_CONDITION_RAINY,  # Freezing Drizzle: Dense intensity
    61: ATTR_CONDITION_RAINY,  # Rain: Slight intensity
    63: ATTR_CONDITION_RAINY,  # Rain: Moderate intensity
    65: ATTR_CONDITION_POURING,  # Rain: Heavy intensity
    66: ATTR_CONDITION_RAINY,  # Freezing Rain: Light intensity
    67: ATTR_CONDITION_POURING,  # Freezing Rain: Heavy intensity
    71: ATTR_CONDITION_SNOWY,  # Snow fall: Slight intensity
    73: ATTR_CONDITION_SNOWY,  # Snow fall: Moderate intensity
    75: ATTR_CONDITION_SNOWY,  # Snow fall: Heavy intensity
    77: ATTR_CONDITION_SNOWY,  # Snow grains
    80: ATTR_CONDITION_RAINY,  # Rain showers: Slight intensity
    81: ATTR_CONDITION_RAINY,  # Rain showers: Moderate intensity
    82: ATTR_CONDITION_POURING,  # Rain showers: Violent intensity
    85: ATTR_CONDITION_SNOWY,  # Snow showers: Slight intensity
    86: ATTR_CONDITION_SNOWY,  # Snow showers: Heavy intensity
    95: ATTR_CONDITION_LIGHTNING,  # Thunderstorm: Slight and moderate intensity
    96: ATTR_CONDITION_LIGHTNING,  # Thunderstorm with slight hail
    99: ATTR_CONDITION_LIGHTNING,  # Thunderstorm with heavy hail
}
