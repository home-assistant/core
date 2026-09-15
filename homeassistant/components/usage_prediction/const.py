"""Constants for the usage prediction integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

from .models import EntityUsageDataCache, EntityUsagePredictions

DOMAIN = "usage_prediction"

# Entities returned per time category when a client does not ask for a specific number
DEFAULT_NUM_RESULTS = 8

# Most a client can ask for, and how many entities per time category are predicted and cached
MAX_NUM_RESULTS = 50

DATA_CACHE: HassKey[
    dict[str, asyncio.Task[EntityUsagePredictions] | EntityUsageDataCache]
] = HassKey("usage_prediction")
