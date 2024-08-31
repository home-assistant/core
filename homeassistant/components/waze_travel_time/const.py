"""Constants for waze_travel_time."""

from __future__ import annotations

DOMAIN = "waze_travel_time"
SEMAPHORE = "semaphore"

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

IMPERIAL_UNITS = "imperial"
METRIC_UNITS = "metric"
UNITS = [METRIC_UNITS, IMPERIAL_UNITS]

REGIONS = ["us", "na", "eu", "il", "au"]
VEHICLE_TYPES = ["car", "taxi", "motorcycle"]

DEFAULT_OPTIONS: dict[str, str | bool] = {
    CONF_REALTIME: DEFAULT_REALTIME,
    CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
    CONF_UNITS: METRIC_UNITS,
    CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
}
