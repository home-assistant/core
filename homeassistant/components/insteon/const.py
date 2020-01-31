"""Constants used by insteon component."""

DOMAIN = "insteon"
INSTEON_ENTITIES = "entities"

CONF_IP_PORT = "ip_port"
CONF_HUB_USERNAME = "username"
CONF_HUB_PASSWORD = "password"
CONF_HUB_VERSION = "hub_version"
CONF_OVERRIDE = "device_override"
CONF_PLM_HUB_MSG = "Must configure either a PLM port or a Hub host"
CONF_CAT = "cat"
CONF_SUBCAT = "subcat"
CONF_FIRMWARE = "firmware"
CONF_PRODUCT_KEY = "product_key"
CONF_X10 = "x10_devices"
CONF_HOUSECODE = "housecode"
CONF_UNITCODE = "unitcode"
CONF_DIM_STEPS = "dim_steps"
CONF_X10_ALL_UNITS_OFF = "x10_all_units_off"
CONF_X10_ALL_LIGHTS_ON = "x10_all_lights_on"
CONF_X10_ALL_LIGHTS_OFF = "x10_all_lights_off"

SRV_ADD_ALL_LINK = "add_all_link"
SRV_DEL_ALL_LINK = "delete_all_link"
SRV_LOAD_ALDB = "load_all_link_database"
SRV_PRINT_ALDB = "print_all_link_database"
SRV_PRINT_IM_ALDB = "print_im_all_link_database"
SRV_X10_ALL_UNITS_OFF = "x10_all_units_off"
SRV_X10_ALL_LIGHTS_OFF = "x10_all_lights_off"
SRV_X10_ALL_LIGHTS_ON = "x10_all_lights_on"
SRV_ALL_LINK_GROUP = "group"
SRV_ALL_LINK_MODE = "mode"
SRV_LOAD_DB_RELOAD = "reload"
SRV_CONTROLLER = "controller"
SRV_RESPONDER = "responder"
SRV_HOUSECODE = "housecode"
SRV_SCENE_ON = "scene_on"
SRV_SCENE_OFF = "scene_off"

SIGNAL_LOAD_ALDB = "load_aldb"
SIGNAL_PRINT_ALDB = "print_aldb"

HOUSECODES = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
]

BUTTON_PRESSED_STATE_NAME = "onLevelButton"
EVENT_BUTTON_ON = "insteon.button_on"
EVENT_BUTTON_OFF = "insteon.button_off"
EVENT_CONF_BUTTON = "button"


STATE_NAME_LABEL_MAP = {
    "keypadButtonA": "Button A",
    "keypadButtonB": "Button B",
    "keypadButtonC": "Button C",
    "keypadButtonD": "Button D",
    "keypadButtonE": "Button E",
    "keypadButtonF": "Button F",
    "keypadButtonG": "Button G",
    "keypadButtonH": "Button H",
    "keypadButtonMain": "Main",
    "onOffButtonA": "Button A",
    "onOffButtonB": "Button B",
    "onOffButtonC": "Button C",
    "onOffButtonD": "Button D",
    "onOffButtonE": "Button E",
    "onOffButtonF": "Button F",
    "onOffButtonG": "Button G",
    "onOffButtonH": "Button H",
    "onOffButtonMain": "Main",
    "fanOnLevel": "Fan",
    "lightOnLevel": "Light",
    "coolSetPoint": "Cool Set",
    "heatSetPoint": "HeatSet",
    "statusReport": "Status",
    "generalSensor": "Sensor",
    "motionSensor": "Motion",
    "lightSensor": "Light",
    "batterySensor": "Battery",
    "dryLeakSensor": "Dry",
    "wetLeakSensor": "Wet",
    "heartbeatLeakSensor": "Heartbeat",
    "openClosedRelay": "Relay",
    "openClosedSensor": "Sensor",
    "lightOnOff": "Light",
    "outletTopOnOff": "Top",
    "outletBottomOnOff": "Bottom",
    "coverOpenLevel": "Cover",
}
