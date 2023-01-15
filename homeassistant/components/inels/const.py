"""Constants for the iNels integration."""
import logging

from homeassistant.const import Platform

DOMAIN = "inels"

BROKER_CONFIG = "inels_mqtt_broker_config"
BROKER = "inels_mqtt_broker"
DEVICES = "devices"

CONF_DISCOVERY_PREFIX = "discovery_prefix"

TITLE = "iNELS"
DESCRIPTION = ""
INELS_VERSION = 1
LOGGER = logging.getLogger(__package__)

DEFAULT_MIN_TEMP = 10.0  # °C
DEFAULT_MAX_TEMP = 50.0  # °C

ICON_TEMPERATURE = "mdi:thermometer"
ICON_BATTERY = "mdi:battery-50"
ICON_SWITCH = "mdi:power-socket-eu"
ICON_LIGHT = "mdi:lightbulb"
ICON_SHUTTER_CLOSED = "mdi:window-shutter"
ICON_SHUTTER_OPEN = "mdi:window-shutter-open"
ICON_BUTTON = "mdi:button-pointer"
ICON_LIGHT_IN = "mdi:brightness-4"
ICON_HUMIDITY = "mdi:water-percent"
ICON_DEW_POINT = "mdi:tailwind"
ICON_PLUS = "mdi:plus"
ICON_MINUS = "mdi:minus"
ICON_ALERT = "mdi:alert"
ICON_PROXIMITY = "mdi:contactless-payment"
ICON_BINARY_INPUT = "mdi:ab-testing"
ICON_FLASH = "mdi:flash"
ICON_FAN = "mdi:fan"
ICON_HEAT_WAVE = "mdi:heat-wave"

ICON_WATER_HEATER_DICT = {
    "on": "mdi:valve-open",
    "off": "mdi:valve-closed",
}

ICON_RELAY_DICT = {
    "on": "mdi:flash",
    "off": "mdi:flash-outline",
}
ICON_TWOCHANNELDIMMER = "mdi:lightbulb-multiple"
ICON_THERMOSTAT = "mdi:home-thermometer-outline"
ICON_BUTTONARRAY = "mdi:button-pointer"

ICONS = {
    Platform.SWITCH: ICON_SWITCH,
    Platform.SENSOR: ICON_TEMPERATURE,
    Platform.BUTTON: ICON_BUTTON,
    Platform.LIGHT: ICON_LIGHT,
}

MANUAL_SETUP = "manual"

BUTTON_PRESS_STATE = "press"
BUTTON_NO_ACTION_STATE = "no_action"

FAN_SPEED_OPTIONS: list[str] = ["Off", "Speed 1", "Speed 2", "Speed 3"]
FAN_SPEED_DICT = {"Off": 0, "Speed 1": 1, "Speed 2": 2, "Speed 3": 3}

SELECT_OPTIONS_DICT = {
    "fan_speed": FAN_SPEED_OPTIONS,
}

SELECT_OPTIONS_ICON = {"fan_speed": ICON_FAN}

SELECT_DICT = {"fan_speed": FAN_SPEED_DICT}
