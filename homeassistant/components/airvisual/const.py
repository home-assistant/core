"""Define constants for the AirVisual component."""
from datetime import timedelta

DOMAIN = 'airvisual'

CONF_CITY = 'city'
CONF_COORDINATES = 'coordinates'
CONF_COUNTRY = 'country'
CONF_LOCATION = 'location'

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

DATA_CLIENT = 'client'
DATA_LISTENER = 'listener'

TOPIC_UPDATE = 'update'
