"""Constants for the GTFS integration."""
from homeassistant.const import CONF_OFFSET, STATE_UNKNOWN, Platform

DOMAIN = "gtfs"

# default values for options
DEFAULT_REFRESH_INTERVAL = 15

DEFAULT_NAME = "GTFS Sensor"
DEFAULT_PATH = "gtfs"

CONF_DATA = "data"
CONF_DESTINATION = "destination"
CONF_ORIGIN = "origin"
CONF_TOMORROW = "include_tomorrow"

PLATFORMS = [Platform.SENSOR]

# constants used in helper
ATTR_ARRIVAL = "arrival"
ATTR_BICYCLE = "trip_bikes_allowed_state"
ATTR_DAY = "day"
ATTR_FIRST = "first"
ATTR_DROP_OFF_DESTINATION = "destination_stop_drop_off_type_state"
ATTR_DROP_OFF_ORIGIN = "origin_stop_drop_off_type_state"
ATTR_INFO = "info"
ATTR_OFFSET = CONF_OFFSET
ATTR_LAST = "last"
ATTR_LOCATION_DESTINATION = "destination_station_location_type_name"
ATTR_LOCATION_ORIGIN = "origin_station_location_type_name"
ATTR_PICKUP_DESTINATION = "destination_stop_pickup_type_state"
ATTR_PICKUP_ORIGIN = "origin_stop_pickup_type_state"
ATTR_ROUTE_TYPE = "route_type_name"
ATTR_TIMEPOINT_DESTINATION = "destination_stop_timepoint_exact"
ATTR_TIMEPOINT_ORIGIN = "origin_stop_timepoint_exact"
ATTR_WHEELCHAIR = "trip_wheelchair_access_available"
ATTR_WHEELCHAIR_DESTINATION = "destination_station_wheelchair_boarding_available"
ATTR_WHEELCHAIR_ORIGIN = "origin_station_wheelchair_boarding_available"

CONF_DATA = "data"
CONF_DESTINATION = "destination"
CONF_ORIGIN = "origin"
CONF_TOMORROW = "include_tomorrow"

BICYCLE_ALLOWED_DEFAULT = STATE_UNKNOWN
BICYCLE_ALLOWED_OPTIONS = {1: True, 2: False}
DROP_OFF_TYPE_DEFAULT = STATE_UNKNOWN
DROP_OFF_TYPE_OPTIONS = {
    0: "Regular",
    1: "Not Available",
    2: "Call Agency",
    3: "Contact Driver",
}
ICON = "mdi:train"
ICONS = {
    0: "mdi:tram",
    1: "mdi:subway",
    2: "mdi:train",
    3: "mdi:bus",
    4: "mdi:ferry",
    5: "mdi:train-variant",
    6: "mdi:gondola",
    7: "mdi:stairs",
    100: "mdi:train",
    101: "mdi:train",
    102: "mdi:train",
    103: "mdi:train",
    104: "mdi:train-car",
    105: "mdi:train",
    106: "mdi:train",
    107: "mdi:train",
    108: "mdi:train",
    109: "mdi:train",
    110: "mdi:train-variant",
    111: "mdi:train-variant",
    112: "mdi:train-variant",
    113: "mdi:train-variant",
    114: "mdi:train-variant",
    115: "mdi:train-variant",
    116: "mdi:train-variant",
    117: "mdi:train-variant",
    200: "mdi:bus",
    201: "mdi:bus",
    202: "mdi:bus",
    203: "mdi:bus",
    204: "mdi:bus",
    205: "mdi:bus",
    206: "mdi:bus",
    207: "mdi:bus",
    208: "mdi:bus",
    209: "mdi:bus",
    400: "mdi:subway-variant",
    401: "mdi:subway-variant",
    402: "mdi:subway",
    403: "mdi:subway-variant",
    404: "mdi:subway-variant",
    405: "mdi:subway-variant",
    700: "mdi:bus",
    701: "mdi:bus",
    702: "mdi:bus",
    703: "mdi:bus",
    704: "mdi:bus",
    705: "mdi:bus",
    706: "mdi:bus",
    707: "mdi:bus",
    708: "mdi:bus",
    709: "mdi:bus",
    710: "mdi:bus",
    711: "mdi:bus",
    712: "mdi:bus-school",
    713: "mdi:bus-school",
    714: "mdi:bus",
    715: "mdi:bus",
    716: "mdi:bus",
    800: "mdi:bus",
    900: "mdi:tram",
    901: "mdi:tram",
    902: "mdi:tram",
    903: "mdi:tram",
    904: "mdi:tram",
    905: "mdi:tram",
    906: "mdi:tram",
    1000: "mdi:ferry",
    1100: "mdi:airplane",
    1200: "mdi:ferry",
    1300: "mdi:airplane",
    1400: "mdi:gondola",
    1500: "mdi:taxi",
    1501: "mdi:taxi",
    1502: "mdi:ferry",
    1503: "mdi:train-variant",
    1504: "mdi:bicycle-basket",
    1505: "mdi:taxi",
    1506: "mdi:car-multiple",
    1507: "mdi:taxi",
    1700: "mdi:train-car",
    1702: "mdi:horse-variant",
}
LOCATION_TYPE_DEFAULT = "Stop"
LOCATION_TYPE_OPTIONS = {
    0: "Station",
    1: "Stop",
    2: "Station Entrance/Exit",
    3: "Other",
}
PICKUP_TYPE_DEFAULT = STATE_UNKNOWN
PICKUP_TYPE_OPTIONS = {
    0: "Regular",
    1: "None Available",
    2: "Call Agency",
    3: "Contact Driver",
}
ROUTE_TYPE_OPTIONS = {
    0: "Tram",
    1: "Subway",
    2: "Rail",
    3: "Bus",
    4: "Ferry",
    5: "Cable Tram",
    6: "Aerial Lift",
    7: "Funicular",
    100: "Railway Service",
    101: "High Speed Rail Service",
    102: "Long Distance Trains",
    103: "Inter Regional Rail Service",
    104: "Car Transport Rail Service",
    105: "Sleeper Rail Service",
    106: "Regional Rail Service",
    107: "Tourist Railway Service",
    108: "Rail Shuttle (Within Complex)",
    109: "Suburban Railway",
    110: "Replacement Rail Service",
    111: "Special Rail Service",
    112: "Lorry Transport Rail Service",
    113: "All Rail Services",
    114: "Cross-Country Rail Service",
    115: "Vehicle Transport Rail Service",
    116: "Rack and Pinion Railway",
    117: "Additional Rail Service",
    200: "Coach Service",
    201: "International Coach Service",
    202: "National Coach Service",
    203: "Shuttle Coach Service",
    204: "Regional Coach Service",
    205: "Special Coach Service",
    206: "Sightseeing Coach Service",
    207: "Tourist Coach Service",
    208: "Commuter Coach Service",
    209: "All Coach Services",
    400: "Urban Railway Service",
    401: "Metro Service",
    402: "Underground Service",
    403: "Urban Railway Service",
    404: "All Urban Railway Services",
    405: "Monorail",
    700: "Bus Service",
    701: "Regional Bus Service",
    702: "Express Bus Service",
    703: "Stopping Bus Service",
    704: "Local Bus Service",
    705: "Night Bus Service",
    706: "Post Bus Service",
    707: "Special Needs Bus",
    708: "Mobility Bus Service",
    709: "Mobility Bus for Registered Disabled",
    710: "Sightseeing Bus",
    711: "Shuttle Bus",
    712: "School Bus",
    713: "School and Public Service Bus",
    714: "Rail Replacement Bus Service",
    715: "Demand and Response Bus Service",
    716: "All Bus Services",
    800: "Trolleybus Service",
    900: "Tram Service",
    901: "City Tram Service",
    902: "Local Tram Service",
    903: "Regional Tram Service",
    904: "Sightseeing Tram Service",
    905: "Shuttle Tram Service",
    906: "All Tram Services",
    1000: "Water Transport Service",
    1100: "Air Service",
    1200: "Ferry Service",
    1300: "Aerial Lift Service",
    1400: "Funicular Service",
    1500: "Taxi Service",
    1501: "Communal Taxi Service",
    1502: "Water Taxi Service",
    1503: "Rail Taxi Service",
    1504: "Bike Taxi Service",
    1505: "Licensed Taxi Service",
    1506: "Private Hire Service Vehicle",
    1507: "All Taxi Services",
    1700: "Miscellaneous Service",
    1702: "Horse-drawn Carriage",
}
TIMEPOINT_DEFAULT = True
TIMEPOINT_OPTIONS = {0: False, 1: True}
WHEELCHAIR_ACCESS_DEFAULT = STATE_UNKNOWN
WHEELCHAIR_ACCESS_OPTIONS = {1: True, 2: False}
WHEELCHAIR_BOARDING_DEFAULT = STATE_UNKNOWN
WHEELCHAIR_BOARDING_OPTIONS = {1: True, 2: False}
