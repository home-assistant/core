"""Constants for the Geocaching integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from geocachingapi.models import GeocachingApiEnvironment

from homeassistant.const import Platform

from .models import GeocachingOAuthApiUrls

DOMAIN: Final = "geocaching"
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

PLATFORMS = [Platform.SENSOR]

# Sensor ID formats
PROFILE_ID_SENSOR_FORMAT = DOMAIN + ".{}_{}"
CACHE_ID_SENSOR_FORMAT = DOMAIN + ".{}_{}"

# Section IDs for the config flow
# Note that changing these will require updating the `strings.json` paths, and recompiling the translations
CONFIG_FLOW_GEOCACHES_SECTION_ID = "tracked_geocache_ids"

# Configuration limits
MAX_TRACKED_CACHES = 25

# Configuration title keys
CACHES_SINGLE_TITLE = "tracked_cache_ref_code"
