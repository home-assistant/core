"""Constants for the usage prediction integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

from .models import EntityUsageDataCache, LocationBasedPredictions

DOMAIN = "usage_prediction"

DATA_CACHE: HassKey[
    dict[str, asyncio.Task[LocationBasedPredictions] | EntityUsageDataCache]
] = HassKey("usage_prediction")
