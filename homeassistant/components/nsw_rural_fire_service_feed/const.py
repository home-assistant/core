"""Define constants for the NSW Rural Fire Service Feeds integration."""
from __future__ import annotations

from homeassistant.const import Platform

CONF_CATEGORIES = "categories"

DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_SCAN_INTERVAL = 300

DOMAIN = "nsw_rural_fire_service_feed"

FEED = "feed"

PLATFORMS = [Platform.GEO_LOCATION]

VALID_CATEGORIES = ["Advice", "Emergency Warning", "Not Applicable", "Watch and Act"]

SIGNAL_DELETE_ENTITY = "nsw_rural_fire_service_feed_delete_{}"
SIGNAL_UPDATE_ENTITY = "nsw_rural_fire_service_feed_update_{}"
