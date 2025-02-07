"""Define constants used throughout the Gryf Smart integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
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
CONF_INPUTS = "input"
CONF_DEVICE_CLASS = "device_class"
CONF_OUT_ID = "o_id"
CONF_TEMP_ID = "t_id"
CONF_HYSTERESIS = "hysteresis"

PLATFORM_PWM = "pwm"
PLATFORM_TEMPERATURE = "temperature"
PLATFORM_INPUT = "input"
PLATFORM_LIGHT = "light"
PLATFORM_BINARY_SENSOR = "binary_input"
PLATFORM_SWITCH = "output"
PLATFORM_THERMOSTAT = "thermostat"

DEFAULT_PORT = "/dev/ttyUSB0"
GRYF_IN_NAME = "Gryf IN"
GRYF_OUT_NAME = "Gryf OUT"

CONFIG_FLOW_MENU_OPTIONS = {
    "add_device": "Add Device",
    "edit_device": "Edit Device",
    "communication": "Setup Communication",
    "finish": "Finish",
}

DEVICE_TYPES = {
    # Platform.COVER: "Shutter",
    Platform.LIGHT: "Lights",
    Platform.SWITCH: "Output",
    # Platform.SENSOR: "Input",
    Platform.BINARY_SENSOR: "Binary input",
    # Platform.LOCK: "Lock",
    # Platform.CLIMATE: "Thermostat",
    Platform.CLIMATE: "Thermostat",
    PLATFORM_PWM: "PWM",
    PLATFORM_TEMPERATURE: "Termometr",
    PLATFORM_INPUT: "Input",
}

CONF_LINE_SENSOR_ICONS = {
    GRYF_IN_NAME: ["mdi:message-arrow-right-outline", "mdi:message-arrow-right"],
    GRYF_OUT_NAME: ["mdi:message-arrow-left-outline", "mdi:message-arrow-left"],
}

BINARY_SENSOR_DEVICE_CLASS = {
    "door": BinarySensorDeviceClass.DOOR,
    "garage door": BinarySensorDeviceClass.GARAGE_DOOR,
    "heat": BinarySensorDeviceClass.HEAT,
    "light": BinarySensorDeviceClass.LIGHT,
    "motion": BinarySensorDeviceClass.MOTION,
    "window": BinarySensorDeviceClass.WINDOW,
    "smoke": BinarySensorDeviceClass.SMOKE,
    "sound": BinarySensorDeviceClass.SOUND,
    "power": BinarySensorDeviceClass.POWER,
    None: BinarySensorDeviceClass.OPENING,
}

SWITCH_DEVICE_CLASS = {
    None: SwitchDeviceClass.SWITCH,
    "switch": SwitchDeviceClass.SWITCH,
    "outlet": SwitchDeviceClass.OUTLET,
}
