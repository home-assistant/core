"""Constants for the HERE Travel Time integration."""
from typing import Final

DOMAIN = "here_travel_time"
DEFAULT_SCAN_INTERVAL = 300


CONF_DESTINATION = "destination"
CONF_DESTINATION_LATITUDE = "destination_latitude"
CONF_DESTINATION_LONGITUDE = "destination_longitude"
CONF_DESTINATION_ENTITY_ID = "destination_entity_id"
CONF_ORIGIN = "origin"
CONF_ORIGIN_LATITUDE = "origin_latitude"
CONF_ORIGIN_LONGITUDE = "origin_longitude"
CONF_ORIGIN_ENTITY_ID = "origin_entity_id"
CONF_ROUTE_MODE = "route_mode"
CONF_ARRIVAL = "arrival"
CONF_DEPARTURE = "departure"
CONF_ARRIVAL_TIME = "arrival_time"
CONF_DEPARTURE_TIME = "departure_time"

DEFAULT_NAME = "HERE Travel Time"

TRAVEL_MODE_BICYCLE = "bicycle"
TRAVEL_MODE_CAR = "car"
TRAVEL_MODE_PEDESTRIAN = "pedestrian"
TRAVEL_MODE_PUBLIC = "publicTransport"
TRAVEL_MODE_TRUCK = "truck"
TRAVEL_MODES = [
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_TRUCK,
]

TRAVEL_MODES_VEHICLE = [TRAVEL_MODE_CAR, TRAVEL_MODE_TRUCK]

ROUTE_MODE_FASTEST = "fastest"
ROUTE_MODE_SHORTEST = "shortest"
ROUTE_MODES = [ROUTE_MODE_FASTEST, ROUTE_MODE_SHORTEST]

ICON_BICYCLE = "mdi:bike"
ICON_CAR = "mdi:car"
ICON_PEDESTRIAN = "mdi:walk"
ICON_PUBLIC = "mdi:bus"
ICON_TRUCK = "mdi:truck"

ICONS = {
    TRAVEL_MODE_BICYCLE: ICON_BICYCLE,
    TRAVEL_MODE_PEDESTRIAN: ICON_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC: ICON_PUBLIC,
    TRAVEL_MODE_TRUCK: ICON_TRUCK,
}

ATTR_DURATION: Final = "duration"
ATTR_DISTANCE: Final = "distance"
ATTR_ORIGIN: Final = "origin"
ATTR_DESTINATION: Final = "destination"

ATTR_DURATION_IN_TRAFFIC: Final = "duration_in_traffic"
ATTR_ORIGIN_NAME: Final = "origin_name"
ATTR_DESTINATION_NAME: Final = "destination_name"
