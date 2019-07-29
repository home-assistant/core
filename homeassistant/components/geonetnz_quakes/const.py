"""Define constants for the GeoNet NZ Quakes integration."""
from datetime import timedelta

DOMAIN = 'geonetnz_quakes'

CONF_MINIMUM_MAGNITUDE = 'minimum_magnitude'
CONF_MMI = 'mmi'

FEED = 'feed'

DEFAULT_MINIMUM_MAGNITUDE = 0.0
DEFAULT_MMI = 2
DEFAULT_RADIUS_IN_KM = 50.0
DEFAULT_UNIT_OF_MEASUREMENT = 'km'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
