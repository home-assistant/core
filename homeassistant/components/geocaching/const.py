"""Constants for the Geocaching integration."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
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


class GeocacheCategory(Enum):
    """Geocaching cache categories."""

    TRACKED = "tracked"
    NEARBY = "nearby"


GEOCACHING_ID_SENSOR_FORMAT = DOMAIN + ".{}_{}"
CACHE_ID_SENSOR_FORMAT = DOMAIN + ".{}_{}_{}"
TRACKABLE_ID_SENSOR_FORMAT = DOMAIN + ".{}_{}"

# Section IDs for the config flow
CONFIG_FLOW_GEOCACHES_SECTION_ID = "tracked_geocache_ids"
CONFIG_FLOW_TRACKABLES_SECTION_ID = "tracked_trackable_ids"
CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID = "nearby_settings"

NEARBY_CACHES_COUNT_TITLE = "Nearby Caches Count"
NEARBY_CACHES_RADIUS_TITLE = "Nearby Caches Radius"

# TODO: Remove this temporary variable, only used during development | pylint: disable=fixme
# Enabling this will skip the entire tracked objects configuration process and use predefined codes
USE_TEST_CONFIG: bool = True
