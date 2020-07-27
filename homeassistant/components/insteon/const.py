"""Constants used by insteon component."""
from pyinsteon.groups import (
    CO_SENSOR,
    COVER,
    DIMMABLE_FAN,
    DIMMABLE_LIGHT,
    DIMMABLE_LIGHT_MAIN,
    DIMMABLE_OUTLET,
    DOOR_SENSOR,
    HEARTBEAT,
    LEAK_SENSOR_WET,
    LIGHT_SENSOR,
    LOW_BATTERY,
    MOTION_SENSOR,
    NEW_SENSOR,
    ON_OFF_OUTLET_BOTTOM,
    ON_OFF_OUTLET_TOP,
    ON_OFF_SWITCH,
    ON_OFF_SWITCH_A,
    ON_OFF_SWITCH_B,
    ON_OFF_SWITCH_C,
    ON_OFF_SWITCH_D,
    ON_OFF_SWITCH_E,
    ON_OFF_SWITCH_F,
    ON_OFF_SWITCH_G,
    ON_OFF_SWITCH_H,
    ON_OFF_SWITCH_MAIN,
    OPEN_CLOSE_SENSOR,
    RELAY,
    SENSOR_MALFUNCTION,
    SMOKE_SENSOR,
    TEST_SENSOR,
)

DOMAIN = "insteon"

INSTEON_COMPONENTS = [
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "light",
    "switch",
]

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
SRV_ADD_DEFAULT_LINKS = "add_default_links"

SIGNAL_LOAD_ALDB = "load_aldb"
SIGNAL_PRINT_ALDB = "print_aldb"
SIGNAL_SAVE_DEVICES = "save_devices"
SIGNAL_ADD_DEFAULT_LINKS = "add_default_links"

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

EVENT_GROUP_ON = "insteon.button_on"
EVENT_GROUP_OFF = "insteon.button_off"
EVENT_GROUP_ON_FAST = "insteon.button_on_fast"
EVENT_GROUP_OFF_FAST = "insteon.button_off_fast"
EVENT_CONF_BUTTON = "button"
ON_OFF_EVENTS = "on_off_events"

STATE_NAME_LABEL_MAP = {
    DIMMABLE_LIGHT_MAIN: "Main",
    ON_OFF_SWITCH_A: "Button A",
    ON_OFF_SWITCH_B: "Button B",
    ON_OFF_SWITCH_C: "Button C",
    ON_OFF_SWITCH_D: "Button D",
    ON_OFF_SWITCH_E: "Button E",
    ON_OFF_SWITCH_F: "Button F",
    ON_OFF_SWITCH_G: "Button G",
    ON_OFF_SWITCH_H: "Button H",
    ON_OFF_SWITCH_MAIN: "Main",
    DIMMABLE_FAN: "Fan",
    DIMMABLE_LIGHT: "Light",
    DIMMABLE_OUTLET: "Outlet",
    MOTION_SENSOR: "Motion",
    LIGHT_SENSOR: "Light",
    LOW_BATTERY: "Battery",
    LEAK_SENSOR_WET: "Wet",
    DOOR_SENSOR: "Door",
    SMOKE_SENSOR: "Smoke",
    CO_SENSOR: "Carbon Monoxide",
    TEST_SENSOR: "Test",
    NEW_SENSOR: "New",
    SENSOR_MALFUNCTION: "Malfunction",
    HEARTBEAT: "Heartbeat",
    OPEN_CLOSE_SENSOR: "Sensor",
    ON_OFF_SWITCH: "Light",
    ON_OFF_OUTLET_TOP: "Top",
    ON_OFF_OUTLET_BOTTOM: "Bottom",
    COVER: "Cover",
    RELAY: "Relay",
}
