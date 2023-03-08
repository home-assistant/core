"""Constants for the iNels integration."""
from dataclasses import dataclass
import logging

from inelsmqtt.const import TEMP_IN, TEMP_OUT

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.light import ColorMode
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfElectricPotential,
    UnitOfTemperature,
)

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
ICON_VALVE = "mdi:valve"
ICON_EYE = "mdi:eye"
ICON_MOTION = "mdi:motion-sensor"
ICON_HOME_FLOOD = "mdi:home-flood"
ICON_CARD_PRESENT = "mdi:smart-card-reader-outline"
ICON_CARD_ID = "mdi:smart-card-outline"

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

# DESCRIPTION KEYWORDS
BINARY_INPUT = "binary_input"
INDEXED = "indexed"
NAME = "name"
ICON = "icon"
DEVICE_CLASS = "device_class"
ENTITY_CATEGORY = "entity_category"
OPTIONS = "options"
OPTIONS_DICT = "options_dict"
UNIT = "unit"
OVERFLOW = "overflow"
RAW_SENSOR_VALUE = "raw_sensor_value"
SUPPORTED_COLOR_MODES = "supported_color_modes"
SUPPORTED_FEATURES = "supported_features"

# BINARY SENSOR PLATFORM
INELS_BINARY_SENSOR_TYPES = {
    "low_battery": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Battery",
        ICON: ICON_BATTERY,
        DEVICE_CLASS: BinarySensorDeviceClass.BATTERY,
    },
    "prox": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Proximity Sensor",
        ICON: ICON_PROXIMITY,
        DEVICE_CLASS: BinarySensorDeviceClass.MOVING,
    },
    "input": {
        BINARY_INPUT: True,
        INDEXED: True,
        NAME: "Binary input sensor",
        ICON: ICON_BINARY_INPUT,
        DEVICE_CLASS: None,
    },
    "heating_out": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Heating output",
        ICON: ICON_HEAT_WAVE,
        DEVICE_CLASS: BinarySensorDeviceClass.RUNNING,
    },
    "detected": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Detector",
        ICON: ICON_EYE,
        DEVICE_CLASS: None,
    },
    "motion": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Motion detector",
        ICON: ICON_MOTION,
        DEVICE_CLASS: BinarySensorDeviceClass.MOTION,
    },
    "flooded": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Flooded",
        ICON: ICON_HOME_FLOOD,
        DEVICE_CLASS: BinarySensorDeviceClass.MOISTURE,
    },
    "card_present": {
        BINARY_INPUT: False,
        INDEXED: False,
        NAME: "Card present",
        ICON: ICON_CARD_PRESENT,
        DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY,
    },
}

# BUTTON PLATFORM
INELS_BUTTON_TYPES = {
    "btn": {
        NAME: "Button",
        ICON: ICON_BUTTON,
    },
    "din": {
        NAME: "Digital input",
        ICON: ICON_BUTTON,
    },
    "sw": {
        NAME: "Switch",
        ICON: ICON_BUTTON,
    },
    "plus": {
        NAME: "Plus",
        ICON: ICON_PLUS,
    },
    "minus": {
        NAME: "Minus",
        ICON: ICON_MINUS,
    },
}

# CLIMATE PLATFORM
INELS_CLIMATE_TYPES = {"climate": {INDEXED: False, NAME: "Thermovalve"}}


@dataclass
class InelsShutterType:
    """Shutter type property description."""

    name: str
    supported_features: CoverEntityFeature


INELS_SHUTTERS_TYPES: dict[str, InelsShutterType] = {
    "shutters": InelsShutterType(
        "Shutter",
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP,
    ),
    "shutters_with_pos": InelsShutterType(
        "Shutter",
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION,
    ),
}

# # SHUTTERS PLATFORM
# INELS_SHUTTERS_TYPES = {
#     "shutters": {
#         NAME: "Shutter",
#         SUPPORTED_FEATURES: [
#             CoverEntityFeature.OPEN,
#             CoverEntityFeature.CLOSE,
#             CoverEntityFeature.STOP,
#         ]
#         # SUPPORTED_FEATURES: CoverEntityFeature.OPEN
#         # | CoverEntityFeature.CLOSE
#         # | CoverEntityFeature.STOP,
#     },
#     "shutters_with_pos": {
#         NAME: "Shutter",
#         SUPPORTED_FEATURES: [
#             CoverEntityFeature.OPEN,
#             CoverEntityFeature.CLOSE,
#             CoverEntityFeature.STOP,
#             CoverEntityFeature.SET_POSITION,
#         ]
#         # SUPPORTED_FEATURES: CoverEntityFeature.OPEN
#         # | CoverEntityFeature.CLOSE
#         # | CoverEntityFeature.STOP
#         # | CoverEntityFeature.SET_POSITION,
#     },
# }

# LIGHT PLATFORM
INELS_LIGHT_TYPES = {
    "out": {
        ICON: ICON_LIGHT,
        NAME: "Light",
        SUPPORTED_FEATURES: [ColorMode.BRIGHTNESS],
    },
    "dali": {
        ICON: ICON_LIGHT,
        NAME: "DALI",
        SUPPORTED_FEATURES: [ColorMode.BRIGHTNESS],
    },
    "aout": {
        ICON: ICON_FLASH,
        NAME: "Analog output",
        SUPPORTED_FEATURES: [ColorMode.BRIGHTNESS],
    },
    "rgb": {
        ICON: ICON_LIGHT,
        NAME: "RGB",
        SUPPORTED_FEATURES: [ColorMode.RGB, ColorMode.BRIGHTNESS],
    },
}

# SELECT PLATFORM
INELS_SELECT_TYPES = {
    "fan_speed": {
        NAME: "Fan speed",
        ICON: ICON_FAN,
        OPTIONS: ["Off", "Speed 1", "Speed 2", "Speed 3"],
        OPTIONS_DICT: {"Off": 0, "Speed 1": 1, "Speed 2": 2, "Speed 3": 3},
    }
}

# SENSOR PLATFORM
INELS_SENSOR_TYPES = {
    "temp": {
        INDEXED: False,
        NAME: "Temperature sensor",
        ICON: ICON_TEMPERATURE,
        UNIT: UnitOfTemperature.CELSIUS,
        RAW_SENSOR_VALUE: False,
    },
    TEMP_IN: {
        INDEXED: False,
        NAME: "Internal temperature sensor",
        ICON: ICON_TEMPERATURE,
        UNIT: UnitOfTemperature.CELSIUS,
        RAW_SENSOR_VALUE: False,
    },
    TEMP_OUT: {
        INDEXED: False,
        NAME: "External temperature sensor",
        ICON: ICON_TEMPERATURE,
        UNIT: UnitOfTemperature.CELSIUS,
        RAW_SENSOR_VALUE: False,
    },
    "light_in": {
        INDEXED: False,
        NAME: "Light intensity",
        ICON: ICON_LIGHT_IN,
        UNIT: LIGHT_LUX,
        RAW_SENSOR_VALUE: False,
    },
    "ain": {
        INDEXED: False,
        NAME: "Analog temperature sensor",
        ICON: ICON_TEMPERATURE,
        UNIT: UnitOfTemperature.CELSIUS,
        RAW_SENSOR_VALUE: False,
    },
    "humidity": {
        INDEXED: False,
        NAME: "Humidity",
        ICON: ICON_HUMIDITY,
        UNIT: PERCENTAGE,
        RAW_SENSOR_VALUE: False,
    },
    "dewpoint": {
        INDEXED: False,
        NAME: "Dew point",
        ICON: ICON_DEW_POINT,
        UNIT: UnitOfTemperature.CELSIUS,
        RAW_SENSOR_VALUE: False,
    },
    "temps": {
        INDEXED: True,
        NAME: "Temperature sensor",
        ICON: ICON_TEMPERATURE,
        UNIT: UnitOfTemperature.CELSIUS,
        RAW_SENSOR_VALUE: False,
    },
    "ains": {
        INDEXED: True,
        NAME: "Analog input",
        ICON: ICON_FLASH,
        UNIT: UnitOfElectricPotential.VOLT,
        RAW_SENSOR_VALUE: False,
    },
    "card_id": {
        INDEXED: False,
        NAME: "Last card ID",
        ICON: ICON_CARD_ID,
        UNIT: None,
        RAW_SENSOR_VALUE: True,
    },
}

# SWITCH PLATFORM
INELS_SWITCH_TYPES = {
    "re": {NAME: "Relay", ICON: ICON_SWITCH, OVERFLOW: "relay_overflow"},
}
