"""Define constants for the GeoJSON events integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "geo_json_events"

PLATFORMS: Final = [Platform.GEO_LOCATION]

ATTR_EXTERNAL_ID: Final = "external_id"
DEFAULT_RADIUS_IN_KM: Final = 20.0
DEFAULT_RADIUS_IN_M: Final = 20000.0
DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=300)
SOURCE: Final = "geo_json_events"

SIGNAL_DELETE_ENTITY: Final = "geo_json_events_delete_{}"
SIGNAL_UPDATE_ENTITY: Final = "geo_json_events_update_{}"
