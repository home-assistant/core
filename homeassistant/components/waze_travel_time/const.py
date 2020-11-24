"""Constants for waze_travel_time."""
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_REGION,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
import homeassistant.helpers.config_validation as cv

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

WAZE_SCHEMA = {
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_REGION): vol.In(REGIONS),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_INCL_FILTER): cv.string,
    vol.Optional(CONF_EXCL_FILTER): cv.string,
    vol.Optional(CONF_REALTIME, default=DEFAULT_REALTIME): cv.boolean,
    vol.Optional(CONF_VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE): vol.In(
        VEHICLE_TYPES
    ),
    vol.Optional(CONF_UNITS): vol.In(UNITS),
    vol.Optional(CONF_AVOID_TOLL_ROADS, default=DEFAULT_AVOID_TOLL_ROADS): cv.boolean,
    vol.Optional(
        CONF_AVOID_SUBSCRIPTION_ROADS, default=DEFAULT_AVOID_SUBSCRIPTION_ROADS
    ): cv.boolean,
    vol.Optional(CONF_AVOID_FERRIES, default=DEFAULT_AVOID_FERRIES): cv.boolean,
}
