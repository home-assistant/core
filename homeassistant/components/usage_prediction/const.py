"""Constants for the usage prediction integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

from .models import EntityUsageDataCache, EntityUsagePredictions

DOMAIN = "usage_prediction"

DATA_CACHE: HassKey[
    dict[str, asyncio.Task[EntityUsagePredictions] | EntityUsageDataCache]
] = HassKey("usage_prediction")
