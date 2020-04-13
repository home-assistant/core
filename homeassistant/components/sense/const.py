"""Constants for monitoring a Sense energy sensor."""

import asyncio

from sense_energy import SenseAPITimeoutException

DOMAIN = "sense"
DEFAULT_TIMEOUT = 10
ACTIVE_UPDATE_RATE = 60
DEFAULT_NAME = "Sense"
SENSE_DATA = "sense_data"
SENSE_DEVICE_UPDATE = "sense_devices_update"
SENSE_DEVICES_DATA = "sense_devices_data"
SENSE_DISCOVERED_DEVICES_DATA = "sense_discovered_devices"
SENSE_TRENDS_COORDINATOR = "sense_trends_coorindator"

ACTIVE_NAME = "Energy"
ACTIVE_TYPE = "active"

ATTRIBUTION = "Data provided by Sense.com"

CONSUMPTION_NAME = "Usage"
CONSUMPTION_ID = "usage"
PRODUCTION_NAME = "Production"
PRODUCTION_ID = "production"

ICON = "mdi:flash"

SENSE_TIMEOUT_EXCEPTIONS = (asyncio.TimeoutError, SenseAPITimeoutException)

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
    "settings": "settings",
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
