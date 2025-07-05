"""Constants for the Mill WiFi Official integration."""

from .device_capability import EPurifierFanMode  # ADDED

DOMAIN = "mill_wifi"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
UPDATE_INTERVAL = 300  # seconds
TOKEN_REFRESH_OFFSET = 60  # seconds

BASE_URL = "https://api.millnorwaycloud.com"
ENDPOINT_AUTH_SIGN_IN = "/customer/auth/sign-in"
ENDPOINT_AUTH_REFRESH = "/customer/auth/refresh"
ENDPOINT_CUSTOMER_SETTINGS = "/customer/check-setting"
ENDPOINT_HOUSE_DEVICES_FORMAT = "/houses/{house_id}/devices"
ENDPOINT_HOUSE_INDEPENDENT_DEVICES_FORMAT = "/houses/{house_id}/devices/independent"
ENDPOINT_DEVICE_DATA_FORMAT = "/devices/{device_id}"
ENDPOINT_DEVICE_SETTINGS_FORMAT = "/devices/{device_id}/settings"

SUPPORTED_CHILD_TYPES = [
    "GL-WIFI Socket G2",
    "GL-WIFI Socket G3",
    "GL-WIFI Socket G4",
    "GL-Sense",
    "GL-Panel Heater G2",
    "GL-Panel Heater G3",
    "GL-Panel Heater G3 M",
    "GL-Panel Heater G3 MV2",
    "GL-Oil Heater G2",
    "GL-Oil Heater G3",
    "GL-Convection Heater G2",
    "GL-Convection Heater G3",
    "GL-WIFI Convection MAX 1500W G3",
    "GL-Air Purifier M",
    "GL-Air Purifier L",
    "GL-Heat Pump",
    "GL-Oil Heater G3 V2",
    "GL-Panel Heater G4",
]

PURIFIER_FAN_MODES = {
    EPurifierFanMode.HARD_OFF.value: "Hard Off",
    EPurifierFanMode.SOFT_OFF.value: "Off",
    EPurifierFanMode.AUTO.value: "Auto",
    EPurifierFanMode.SLEEP.value: "Night",
    EPurifierFanMode.BOOST.value: "Boost",
    EPurifierFanMode.MANUAL_LEVEL1.value: "Manual Level 1",
    EPurifierFanMode.MANUAL_LEVEL2.value: "Manual Level 2",
    EPurifierFanMode.MANUAL_LEVEL3.value: "Manual Level 3",
    EPurifierFanMode.MANUAL_LEVEL4.value: "Manual Level 4",
    EPurifierFanMode.MANUAL_LEVEL5.value: "Manual Level 5",
    EPurifierFanMode.MANUAL_LEVEL6.value: "Manual Level 6",
    EPurifierFanMode.MANUAL_LEVEL7.value: "Manual Level 7",
}

FILTER_STATE_OK = "OK"
FILTER_STATE_MEDIUM_DIRTY = "MEDIUM_DIRTY"
FILTER_STATE_DIRTY = "DIRTY"
FILTER_STATE_MUST_BE_CHANGED = "MUST_BE_CHANGED"
FILTER_STATE_UNKNOWN = "UNKNOWN"

FILTER_STATES = [
    FILTER_STATE_OK,
    FILTER_STATE_MEDIUM_DIRTY,
    FILTER_STATE_DIRTY,
    FILTER_STATE_MUST_BE_CHANGED,
    FILTER_STATE_UNKNOWN,
]
