"""Define constants used throughout the Gryf Smart integration."""

from enum import Enum

from homeassistant.const import Platform

DOMAIN = "gryfsmart"

CONF_MODULE_COUNT = "module_count"
CONF_PORT = "port"
CONF_TYPE = "type"
CONF_ID = "id"
CONF_PIN = "pin"
CONF_NAME = "name"
CONF_EXTRA = "extra parameters"
CONF_DEVICES = "devices"
CONF_RECONFIGURE = "reconfigure"
CONF_COMMUNICATION = "communication"
CONF_API = "api"
CONF_DEVICE_DATA = "device_data"

PLATFORM_PWM = "pwm"
PLATFORM_TEMPERATURE = "temperature"

DEFAULT_PORT = "/dev/ttyUSB0"

CONFIG_FLOW_MENU_OPTIONS = {
    "add_device": "Add Device",
    "edit_device": "Edit Device",
    "communication": "Setup Communication",
    "finish": "Finish",
}

DEVICE_TYPES = {
    Platform.COVER: "Shutter",
    Platform.LIGHT: "Lights",
    Platform.SWITCH: "Outputs",
    Platform.SENSOR: "Input",
    Platform.BINARY_SENSOR: "Binary input",
    Platform.LOCK: "Lock",
    Platform.CLIMATE: "Thermostat",
    PLATFORM_PWM: "PWM",
    PLATFORM_TEMPERATURE: "Termometr",
}

CONF_TILT = "tilt"
CONF_LIGHTS = "lights"
CONF_BUTTON = "buttons"
CONF_SERIAL = "port"
CONF_DOORS = "doors"
CONF_WINDOW = "windows"
CONF_TEMPERATURE = "temperature"
CONF_COVER = "covers"
CONF_TIME = "time"
CONF_LOCK = "lock"
CONF_PWM = "pwm"
CONF_CLIMATE = "climate"
CONF_HARMONOGRAM = "harmonogram"
CONF_T_ID = "t_id"
CONF_O_ID = "o_id"
CONF_T_PIN = "t_pin"
CONF_O_PIN = "o_pin"
CONF_ID_COUNT = "id"
CONF_GATE = "gate"
CONF_P_COVER = "p_covers"
CONF_IP = "ip"
CONF_STATES_UPDATE = "states_update"
CONF_HARMONOGRAM = "harmonogram"
CONF_ON = "on"
CONF_OFF = "off"
CONF_ALL = "all"


class OUTPUT_STATES(Enum):
    """Output states enum."""

    OFF = "2"
    ON = "1"
    TOGGLE = "3"
