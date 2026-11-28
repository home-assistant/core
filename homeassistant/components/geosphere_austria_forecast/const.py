"""Constants for the GeoSphere Austria Forecast integration."""

import asyncio

from homeassistant.util.hass_dict import HassKey

DOMAIN = "geosphere_austria_forecast"
# The API can take tens of seconds to answer, longer than the client default.
REQUEST_TIMEOUT = 60
# The API allows five requests per second for all locations together.
MAX_REQUESTS_PER_SECOND = 5
REQUEST_SLOTS: HassKey[asyncio.Semaphore] = HassKey(DOMAIN)
