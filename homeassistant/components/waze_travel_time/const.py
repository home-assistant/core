"""Constants for waze_travel_time."""
from homeassistant.const import CONF_UNIT_SYSTEM_IMPERIAL, CONF_UNIT_SYSTEM_METRIC

DOMAIN = "waze_travel_time"

ATTR_DESTINATION = "destination"
ATTR_DURATION = "duration"
ATTR_DISTANCE = "distance"
ATTR_ORIGIN = "origin"
ATTR_ROUTE = "route"

ATTRIBUTION = "Powered by Waze"

CONF_DESTINATION = "destination"
CONF_ORIGIN = "origin"
CONF_INCL_FILTER = "incl_filter"
CONF_EXCL_FILTER = "excl_filter"
CONF_REALTIME = "realtime"
CONF_UNITS = "units"
CONF_VEHICLE_TYPE = "vehicle_type"
CONF_AVOID_TOLL_ROADS = "avoid_toll_roads"
CONF_AVOID_SUBSCRIPTION_ROADS = "avoid_subscription_roads"
CONF_AVOID_FERRIES = "avoid_ferries"

DEFAULT_NAME = "Waze Travel Time"
DEFAULT_REALTIME = True
DEFAULT_VEHICLE_TYPE = "car"
DEFAULT_AVOID_TOLL_ROADS = False
DEFAULT_AVOID_SUBSCRIPTION_ROADS = False
DEFAULT_AVOID_FERRIES = False

ICON = "mdi:car"

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

REGIONS = ["US", "NA", "EU", "IL", "AU"]
VEHICLE_TYPES = ["car", "taxi", "motorcycle"]

# Attempt to find entity_id without finding address with period.
ENTITY_ID_PATTERN = "(?<![a-zA-Z0-9 ])[a-z_]+[.][a-zA-Z0-9_]+"
