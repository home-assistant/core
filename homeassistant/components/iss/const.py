"""Constants for iss."""

DOMAIN = "iss"

DEFAULT_NAME = "ISS"

# Update people data every X hours
CONF_PEOPLE_UPDATE_HOURS = "people_update_hours"

# By default, how often to update people information
DEFAULT_PEOPLE_UPDATE_HOURS = 24

# Don't allow someone to configure the people update
# Interval to anything smaller than this.
MIN_PEOPLE_UPDATE_HOURS = 1

# Configuration key for position update interval (in seconds)
CONF_POSITION_UPDATE_SECONDS = "position_update_seconds"

# By default, how often to update ISS position (in seconds)
DEFAULT_POSITION_UPDATE_SECONDS = 60

# Minimum position update interval (in seconds)
MIN_POSITION_UPDATE_SECONDS = 1

# Request timeout for external API calls (seconds)
REQUEST_TIMEOUT_SECONDS = 30

# TLE data sources (plain text only, no authentication or zip files)
TLE_SOURCES = {
    "mstl": "http://mstl.atl.calpoly.edu/~ops/keps/kepler.txt",
    "amsat": "https://www.amsat.org/amsat/ftp/keps/current/nasabare.txt",
    "celestrak": "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
}

# Default enabled TLE sources
DEFAULT_TLE_SOURCES = ["mstl", "amsat", "celestrak"]

# Configuration keys for TLE sources
CONF_TLE_SOURCES = "tle_sources"
