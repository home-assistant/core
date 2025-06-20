"""Define constants for the GeoNet NZ Quakes integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "geonetnz_quakes"

PLATFORMS = [Platform.GEO_LOCATION, Platform.SENSOR]

CONF_MINIMUM_MAGNITUDE = "minimum_magnitude"
CONF_MMI = "mmi"

DEFAULT_FILTER_TIME_INTERVAL = timedelta(days=7)
DEFAULT_MINIMUM_MAGNITUDE = 0.0
DEFAULT_MMI = 3
DEFAULT_RADIUS = 50.0
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
