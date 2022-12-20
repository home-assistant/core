"""The nsw_rural_fire_service_feed component."""

import voluptuous as vol

from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CATEGORIES,
    DEFAULT_RADIUS_IN_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    VALID_CATEGORIES,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(
                    float
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(CONF_CATEGORIES, default=[]): vol.All(
                    cv.ensure_list, [vol.In(VALID_CATEGORIES)]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
