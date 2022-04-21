"""Define constants for the GeoJSON events integration."""
from typing import Final

from homeassistant.const import Platform

DOMAIN = "geo_json_events"

ATTR_EXTERNAL_ID = "external_id"
ATTR_CREATED = "created"
ATTR_LAST_UPDATE = "last_update"
ATTR_LAST_UPDATE_SUCCESSFUL = "last_update_successful"
ATTR_LAST_TIMESTAMP = "last_timestamp"
ATTR_REMOVED = "removed"
ATTR_STATUS = "status"
ATTR_UPDATED = "updated"

DEFAULT_FORCE_UPDATE: Final = True
DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_SCAN_INTERVAL = 300
DEFAULT_UNIT_OF_MEASUREMENT = "events"

FEED = "feed"
SOURCE = "geo_json_events"

PLATFORMS = [Platform.SENSOR, Platform.GEO_LOCATION]
