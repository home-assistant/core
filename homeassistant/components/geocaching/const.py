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
# Note that changing these will require updating the `strings.json` paths, and recompiling the translations
CONFIG_FLOW_GEOCACHES_SECTION_ID = "tracked_geocache_ids"
CONFIG_FLOW_TRACKABLES_SECTION_ID = "tracked_trackable_ids"
CONFIG_FLOW_NEARBY_SETTINGS_SECTION_ID = "nearby_settings"

# Configuration limits
MAX_NEARBY_CACHES = 25
MAX_TRACKED_CACHES = 25
MAX_TRACKABLES = 10

CACHES_SINGLE_TITLE = "tracked_cache_ref_code"
TRACKABLES_SINGLE_TITLE = "tracked_trackable_ref_code"

NEARBY_CACHES_COUNT_TITLE = "nearby_caches_max_count"
NEARBY_CACHES_RADIUS_TITLE = "nearby_caches_radius"

# TODO: Remove this temporary variable, only used during development | pylint: disable=fixme
# Enabling this will skip the entire tracked objects configuration process and use predefined codes
USE_TEST_CONFIG: bool = True
