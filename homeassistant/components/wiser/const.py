"""
Constants  for Wiser Platform.

https://github.com/asantaga/wiserHomeAssistantPlatform
Angelosantagata@gmail.com

"""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "wiser"
DATA_WISER_CONFIG = "wiser_config"
VERSION = "1.3.1"
WISER_PLATFORMS = ["climate", "sensor", "switch"]
DATA = "data"
UPDATE_TRACK = "update_track"
UPDATE_LISTENER = "update_listener"

# Battery Constants

TRV_FULL_BATTERY_LEVEL = 30
TRV_MIN_BATTERY_LEVEL = 25
ROOMSTAT_MIN_BATTERY_LEVEL = 17
ROOMSTAT_FULL_BATTERY_LEVEL = 27


# Hub
HUBNAME = "Wiser Heat Hub"
MANUFACTURER = "Drayton Wiser"
ROOM = "Room"

# Notifications
NOTIFICATION_ID = "wiser_notification"
NOTIFICATION_TITLE = "Wiser Component Setup"

# Default Values
DEFAULT_BOOST_TEMP = 2
DEFAULT_BOOST_TEMP_TIME = 60
DEFAULT_SCAN_INTERVAL = 30

# Custom Configs
CONF_BOOST_TEMP: str = "boost_temp"
CONF_BOOST_TEMP_TIME = "boost_time"


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
WEEKENDS = ["saturday", "sunday"]
SPECIALDAYS = ["weekdays", "weekends"]

WISER_SWITCHES = [
    {
        "name": "Valve Protection",
        "key": "ValveProtectionEnabled",
        "icon": "mdi:snowflake-alert",
    },
    {"name": "Eco Mode", "key": "EcoModeEnabled", "icon": "mdi:leaf"},
    {
        "name": "Away Mode Affects Hot Water",
        "key": "AwayModeAffectsHotWater",
        "icon": "mdi:water",
    },
    {"name": "Comfort Mode", "key": "ComfortModeEnabled", "icon": "mdi:sofa"},
    {"name": "Away Mode", "key": "OverrideType", "icon": "mdi:beach"},
]


SIGNAL_STRENGTH_ICONS = {
    "NoSignal": "mdi:wifi-strength-alert-outline",
    "Poor": "mdi:wifi-strength-1",
    "Medium": "mdi:wifi-strength-2",
    "Good": "mdi:wifi-strength-3",
    "VeryGood": "mdi:wifi-strength-4",
}

WISER_SERVICES = {
    "SERVICE_BOOST_HEATING": "boost_heating",
    "SERVICE_COPY_SCHEDULE": "copy_schedule",
    "SERVICE_GET_SCHEDULE": "get_schedule",
    "SERVICE_SET_SCHEDULE": "set_schedule",
    "SERVICE_SET_SMARTPLUG_MODE": "set_smartplug_mode",
    "SERVICE_SET_HOTWATER_MODE": "set_hotwater_mode",
}
