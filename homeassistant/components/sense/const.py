"""Constants for monitoring a Sense energy sensor."""

import socket

from sense_energy import (
    SenseAPIException,
    SenseAPITimeoutException,
    SenseWebsocketException,
)

DOMAIN = "sense"
DEFAULT_TIMEOUT = 30
ACTIVE_UPDATE_RATE = 60
DEFAULT_NAME = "Sense"
SENSE_DEVICE_UPDATE = "sense_devices_update"

ACTIVE_NAME = "Energy"
ACTIVE_TYPE = "active"

ATTRIBUTION = "Data provided by Sense.com"

CONSUMPTION_NAME = "Usage"
CONSUMPTION_ID = "usage"
PRODUCTION_NAME = "Production"
PRODUCTION_ID = "production"
PRODUCTION_PCT_NAME = "Net Production Percentage"
PRODUCTION_PCT_ID = "production_pct"
NET_PRODUCTION_NAME = "Net Production"
NET_PRODUCTION_ID = "net_production"
TO_GRID_NAME = "To Grid"
TO_GRID_ID = "to_grid"
FROM_GRID_NAME = "From Grid"
FROM_GRID_ID = "from_grid"
SOLAR_POWERED_NAME = "Solar Powered Percentage"
SOLAR_POWERED_ID = "solar_powered"

SENSE_TIMEOUT_EXCEPTIONS = (TimeoutError, SenseAPITimeoutException)
SENSE_WEBSOCKET_EXCEPTIONS = (socket.gaierror, SenseWebsocketException)
SENSE_CONNECT_EXCEPTIONS = (
    socket.gaierror,
    TimeoutError,
    SenseAPITimeoutException,
    SenseAPIException,
)

MDI_ICONS = {
    "ac": "air-conditioner",
    "aquarium": "fish",
    "car": "car-electric",
    "computer": "desktop-classic",
    "cup": "coffee",
    "dehumidifier": "water-off",
    "dishes": "dishwasher",
    "drill": "toolbox",
    "fan": "fan",
    "freezer": "fridge-top",
    "fridge": "fridge-bottom",
    "game": "gamepad-variant",
    "garage": "garage",
    "grill": "stove",
    "heat": "fire",
    "heater": "radiatior",
    "humidifier": "water",
    "kettle": "kettle",
    "leafblower": "leaf",
    "lightbulb": "lightbulb",
    "media_console": "set-top-box",
    "modem": "router-wireless",
    "outlet": "power-socket-us",
    "papershredder": "shredder",
    "printer": "printer",
    "pump": "water-pump",
    "settings": "cog",
    "skillet": "pot",
    "smartcamera": "webcam",
    "socket": "power-plug",
    "solar_alt": "solar-power",
    "sound": "speaker",
    "stove": "stove",
    "trash": "trash-can",
    "tv": "television",
    "vacuum": "robot-vacuum",
    "washer": "washing-machine",
}
