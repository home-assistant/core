"""Constants for the GeoSphere Austria Forecast integration."""

DOMAIN = "geosphere_austria_forecast"
SUBENTRY_TYPE_LOCATION = "location"
# The API can take tens of seconds to answer, longer than the client default.
REQUEST_TIMEOUT = 60
# Requests at a time; the API allows five requests per second.
MAX_PARALLEL_REQUESTS = 5
