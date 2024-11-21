"""Constants for the Geocaching integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from geocachingapi.models import GeocachingApiEnvironment

from homeassistant.const import Platform

from .models import GeocachingOAuthApiUrls

DOMAIN: Final = "geocaching"
PLATFORMS = [Platform.SENSOR]
LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(hours=1)

ENVIRONMENT_URLS = {
    GeocachingApiEnvironment.Staging: GeocachingOAuthApiUrls(
        authorize_url="https://staging.geocaching.com/oauth/authorize.aspx",
        token_url="https://oauth-staging.geocaching.com/token",
    ),
    GeocachingApiEnvironment.Production: GeocachingOAuthApiUrls(
        authorize_url="https://www.geocaching.com/oauth/authorize.aspx",
        token_url="https://oauth.geocaching.com/token",
    ),
}

ENVIRONMENT = GeocachingApiEnvironment.Production

GEOCACHING_ID_SENSOR_FORMAT = DOMAIN + ".{}_{}"
NEARBY_CACHE_ID_SENSOR_FORMAT = DOMAIN + ".nearby_{}"
TRACKED_CACHE_ID_SENSOR_FORMAT = DOMAIN + ".tracked_{}"
TRACKED_TRACKABLE_ID_SENSOR_FORMAT = DOMAIN + ".trackable_{}"
