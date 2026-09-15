"""Constants for the usage prediction integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

from .models import EntityUsageDataCache, EntityUsagePredictions

DOMAIN = "usage_prediction"

DEFAULT_LIMIT = 8

# Predicted and cached at the maximum so any requested limit is served from the cache
MAX_LIMIT = 50

DATA_CACHE: HassKey[
    dict[str, asyncio.Task[EntityUsagePredictions] | EntityUsageDataCache]
] = HassKey("usage_prediction")
