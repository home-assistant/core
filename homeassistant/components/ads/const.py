"""Support for Automation Device Specification (ADS).

This module defines constants, enumerations, and key classes used for
the ADS integration in Home Assistant.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import pyads

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    Platform,
)
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .hub import AdsHub

# Domain and data key
DOMAIN = "ads"
DATA_ADS: HassKey[AdsHub] = HassKey(DOMAIN)

# Configuration constants
CONF_ADS_DEVICE = CONF_DEVICE
CONF_ADS_IP_ADDRESS = CONF_IP_ADDRESS
CONF_ADS_PORT = CONF_PORT
CONF_ADS_HUB = "adshub"
CONF_ADS_AMSNETID = "amsnetid"
CONF_ADS_TIMEOUT = CONF_TIMEOUT
CONF_ADS_RETRY = "retry"
CONF_ADS_TEMPLATE = "template"
CONF_ADS_SYMBOLS = "symbols"
CONF_ADS_FIELDS = "fields"
CONF_ADS_NAME = CONF_NAME
CONF_ADS_VAR_NAME = "adsvar_name"
CONF_ADS_VAR_DEVICE_TYPE = "adsvar_devicetype"
CONF_ADS_VAR_ERROR = "adsvar_error"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VAR = "adsvar"
CONF_ADS_VALUE = "value"
CONF_ADS_TYPE_MODE = "adstype_mode"
CONF_ADS_DEVICE_CLASS = "device_class"
CONF_ADS_FACTOR = "factor"
CONF_ADS_UNIT_OF_MEASUREMENT = "unit_of_measurement"
CONF_ADS_HUB_DEFAULT = "HUB1"
CONF_ADS_APPTIMESTAMP = "TwinCAT_SystemInfoVarList._AppInfo.AppTimestamp"

SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

# State keys
STATE_KEY_STATE = "state"
STATE_KEY_BRIGHTNESS = "brightness"
STATE_KEY_COLOR_TEMP_KELVIN = "color_temp_kelvin"
STATE_KEY_HUE = "hue"
STATE_KEY_SATURATION = "saturation"
STATE_KEY_COLOR_MODE = "color_mode"
STATE_KEY_POSITION = "position"
STATE_KEY_TILT_POSITION = "tilt_position"
STATE_KEY_CURRENT_TEMP = "current_temp"
STATE_KEY_TARGET_TEMP = "target_temp"
STATE_KEY_HVAC_MODE = "hvac_mode"


class AdsType(StrEnum):
    """Enumeration of supported ADS types."""

    BOOL = "bool"
    BYTE = "byte"
    INT = "int"
    UINT = "uint"
    SINT = "sint"
    USINT = "usint"
    DINT = "dint"
    UDINT = "udint"
    WORD = "word"
    DWORD = "dword"
    LREAL = "lreal"
    REAL = "real"
    STRING = "string"
    TIME = "time"
    DATE = "date"
    DATE_AND_TIME = "dt"
    TOD = "tod"


class AdsState(StrEnum):
    """Enumeration of supported ADS states."""

    INVALID = "Invalid"
    IDLE = "Idle"
    RESET = "Reset"
    INIT = "Init"
    START = "Start"
    RUN = "Run"
    STOP = "Stop"
    SAVECFG = "Save Config"
    LOADCFG = "Load Config"
    POWERFAILURE = "Power Failure"
    POWERGOOD = "Power Good"
    ERROR = "Error"
    SHUTDOWN = "Shutdown"
    SUSPEND = "Suspend"
    RESUME = "Resume"
    CONFIG = "Config"
    RECONFIG = "Reconfig"


ADS_TYPEMAP = {
    AdsType.BOOL: pyads.PLCTYPE_BOOL,
    AdsType.BYTE: pyads.PLCTYPE_BYTE,
    AdsType.INT: pyads.PLCTYPE_INT,
    AdsType.UINT: pyads.PLCTYPE_UINT,
    AdsType.SINT: pyads.PLCTYPE_SINT,
    AdsType.USINT: pyads.PLCTYPE_USINT,
    AdsType.DINT: pyads.PLCTYPE_DINT,
    AdsType.UDINT: pyads.PLCTYPE_UDINT,
    AdsType.WORD: pyads.PLCTYPE_WORD,
    AdsType.DWORD: pyads.PLCTYPE_DWORD,
    AdsType.REAL: pyads.PLCTYPE_REAL,
    AdsType.LREAL: pyads.PLCTYPE_LREAL,
    AdsType.STRING: pyads.PLCTYPE_STRING,
    AdsType.TIME: pyads.PLCTYPE_TIME,
    AdsType.DATE: pyads.PLCTYPE_DATE,
    AdsType.DATE_AND_TIME: pyads.PLCTYPE_DT,
    AdsType.TOD: pyads.PLCTYPE_TOD,
}

ADS_STATEMAP = {
    AdsState.INVALID: pyads.ADSSTATE_INVALID,
    AdsState.IDLE: pyads.ADSSTATE_IDLE,
    AdsState.RESET: pyads.ADSSTATE_RESET,
    AdsState.INIT: pyads.ADSSTATE_INIT,
    AdsState.START: pyads.ADSSTATE_START,
    AdsState.RUN: pyads.ADSSTATE_RUN,
    AdsState.STOP: pyads.ADSSTATE_STOP,
    AdsState.SAVECFG: pyads.ADSSTATE_SAVECFG,
    AdsState.LOADCFG: pyads.ADSSTATE_LOADCFG,
    AdsState.POWERFAILURE: pyads.ADSSTATE_POWERFAILURE,
    AdsState.POWERGOOD: pyads.ADSSTATE_POWERGOOD,
    AdsState.ERROR: pyads.ADSSTATE_ERROR,
    AdsState.SHUTDOWN: pyads.ADSSTATE_SHUTDOWN,
    AdsState.SUSPEND: pyads.ADSSTATE_SUSPEND,
    AdsState.RESUME: pyads.ADSSTATE_RESUME,
    AdsState.CONFIG: pyads.ADSSTATE_CONFIG,
    AdsState.RECONFIG: pyads.ADSSTATE_RECONFIG,
}


class AdsDiscoveryKeys:
    """Constants for ADS discovery keys used for device identification."""

    NAME = CONF_ADS_NAME
    DEVICE_TYPE = "devicetype"
    ADSPATH = "adspath"
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE


class AdsLightKeys:
    """Constants for ADS light platform configuration keys."""

    PLATFORM = Platform.LIGHT.value
    DEFAULT_NAME = "ADS Light"
    NAME = CONF_ADS_NAME
    TYPE = CONF_ADS_TYPE
    TYPE_MODE = CONF_ADS_TYPE_MODE
    VAR = CONF_ADS_VAR
    VAR_BRIGHTNESS = "adsvar_brightness"
    VAL_MIN_BRIGHTNESS = "adsval_min_brightness"
    VAL_MAX_BRIGHTNESS = "adsval_max_brightness"
    VAR_COLOR_TEMP_KELVIN = "adsvar_color_temp_kelvin"
    VAL_MIN_COLOR_TEMP_KELVIN = "adsval_min_color_temp_kelvin"
    VAL_MAX_COLOR_TEMP_KELVIN = "adsval_max_color_temp_kelvin"
    VAR_HUE = "adsvar_hue"
    VAR_SATURATION = "adsvar_saturation"
    VAR_COLOR_MODE = "adsvar_color_mode"
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsSwitchKeys:
    """Constants for ADS switch platform configuration keys."""

    PLATFORM = Platform.SWITCH.value
    DEFAULT_NAME = "ADS Switch"
    NAME = CONF_ADS_NAME
    TYPE = CONF_ADS_TYPE
    VAR = CONF_ADS_VAR
    DEVICE_CLASS = CONF_ADS_DEVICE_CLASS
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsClimateKeys:
    """Constants for ADS climate platform configuration keys."""

    PLATFORM = Platform.CLIMATE.value
    DEFAULT_NAME = "ADS Climate"
    NAME = CONF_ADS_NAME
    TYPE = CONF_ADS_TYPE
    TYPE_MODE = CONF_ADS_TYPE_MODE
    VAR_CURRENT_TEMPERATURE = "adsvar_current_temperature"
    VAR_TARGET_TEMPERATURE = "adsvar_target_temperature"
    VAR_HVAC_MODE = "adsvar_hvac_mode"
    HVAC_MODES = "hvac_modes"
    UNIT_OF_MEASUREMENT = CONF_ADS_UNIT_OF_MEASUREMENT
    DEVICE_CLASS = CONF_ADS_DEVICE_CLASS
    FACTOR = CONF_ADS_FACTOR
    VAL_MIN_TEMPERATURE = "adsval_min_temperature"
    VAL_MAX_TEMPERATURE = "adsval_max_temperature"
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsCoverKeys:
    """Constants for ADS cover platform configuration keys."""

    PLATFORM = Platform.COVER.value
    DEFAULT_NAME = "ADS Cover"
    NAME = CONF_ADS_NAME
    TYPE = CONF_ADS_TYPE
    VAR = CONF_ADS_VAR
    VAR_POSITION = "adsvar_position"
    VAR_SET_POSITION = "adsvar_set_position"
    VAR_TILT = "adsvar_tilt"
    VAR_SET_TILT = "adsvar_set_tilt"
    VAR_OPEN = "adsvar_open"
    VAR_CLOSE = "adsvar_close"
    VAR_STOP = "adsvar_stop"
    VAR_OPEN_TILT = "adsvar_open_tilt"
    VAR_CLOSE_TILT = "adsvar_close_tilt"
    VAL_OPEN_POSITION = "adsval_open_position"
    VAL_CLOSE_POSITION = "adsval_close_position"
    VAL_OPEN_TILT = "adsval_open_tilt"
    VAL_CLOSE_TILT = "adsval_close_tilt"
    DEVICE_CLASS = CONF_ADS_DEVICE_CLASS
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsSensorKeys:
    """Constants for ADS sensor platform configuration keys."""

    PLATFORM = Platform.SENSOR.value
    DEFAULT_NAME = "ADS Sensor"
    NAME = CONF_ADS_NAME
    TYPE = CONF_ADS_TYPE
    VAR = CONF_ADS_VAR
    FACTOR = CONF_ADS_FACTOR
    DEVICE_CLASS = CONF_ADS_DEVICE_CLASS
    STATE_CLASS = "state_class"
    UNIT_OF_MEASUREMENT = CONF_ADS_UNIT_OF_MEASUREMENT
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsBinarySensorKeys:
    """Constants for ADS binary sensor platform configuration keys."""

    PLATFORM = Platform.BINARY_SENSOR.value
    DEFAULT_NAME = "ADS Binary Sensor"
    NAME = CONF_ADS_NAME
    VAR = CONF_ADS_VAR
    DEVICE_CLASS = CONF_ADS_DEVICE_CLASS
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsValveKeys:
    """Constants for ADS valve platform configuration keys."""

    PLATFORM = Platform.VALVE.value
    DEFAULT_NAME = "ADS Valve"
    NAME = CONF_ADS_NAME
    VAR = CONF_ADS_VAR
    DEVICE_CLASS = CONF_ADS_DEVICE_CLASS
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsSelectKeys:
    """Constants for ADS select platform configuration keys."""

    PLATFORM = Platform.SELECT.value
    DEFAULT_NAME = "ADS Select"
    NAME = CONF_ADS_NAME
    VAR = CONF_ADS_VAR
    OPTIONS = "options"
    VAR_NAME = CONF_ADS_VAR_NAME
    VAR_DEVICE_TYPE = CONF_ADS_VAR_DEVICE_TYPE
    VAR_ERROR = CONF_ADS_VAR_ERROR


class AdsDefaultTemplate:
    """Default template values for ADS integrations.

    Contains default structure names, variable names, and default numeric values.
    """

    STRUCT_LIGHT = "Tc3_IoT_BA.ST_IoT_Control_Light"
    STRUCT_SWITCH = "Tc3_IoT_BA.ST_IoT_Control_Switch"
    STRUCT_CLIMATE = "Tc3_IoT_BA.ST_IoT_Control_Thermostat"
    STRUCT_COVER = "Tc3_IoT_BA.ST_IoT_Control_Blind"
    STRUCT_SENSOR = "Tc3_IoT_BA.ST_IoT_Control_Sensor"
    STRUCT_BINARY_SENSOR = "Tc3_IoT_BA.ST_IoT_Control_Sensor"
    STRUCT_VALVE = "Tc3_IoT_BA.ST_IoT_Control_Valve"
    VAR_NAME = "sName"
    VAR_STATE = "bOn"
    VAR_VALUE = "fValue"
    VAR_HVAC_MODE = "eActiveHVACMode"
    VAR_COLOR_MODE = "eActiveColorMode"
    VAR_BRIGHTNESS = "nBrightness"
    VAR_COLOR_TEMP_KELVIN = "nColorTemperature"
    VAR_HUE = "nHue"
    VAR_SATURATION = "nSaturation"
    VAR_DEVICE_TYPE = "eDeviceType"
    VAR_TEMP = "rCurrentTemperature"
    VAR_SET_TEMP = "rTargetTemperature"
    VAR_IS_CLOSED = "bClosed"
    VAR_POSITION = "nCurrentPosition"
    VAR_SET_POSITION = "nTargetPosition"
    VAR_TILT = "nCurrentTiltAngle"
    VAR_SET_TILT = "nTargetTiltAngle"
    VAR_OPEN = "bPositionUp"
    VAR_CLOSE = "bPositionDown"
    VAR_STOP = "bHoldPosition"
    VAR_OPEN_TILT = "bAngleLimitDown"
    VAR_CLOSE_TILT = "bAngleLimitUp"
    VAR_ERROR = "eError"
    TYPE_UNSIGNED_INTEGER = "uint"
    TYPE_FLOAT = "real"
    UNIT_OF_TEMPERATURE = "°C"
    STATE_CLASS = SensorStateClass.MEASUREMENT.value
    VAL_MIN_BRIGHTNESS = 0
    VAL_MAX_BRIGHTNESS = 100
    VAL_MIN_COLOR_TEMP_KELVIN = 2400
    VAL_MAX_COLOR_TEMP_KELVIN = 6500
    VAL_MIN_TEMP = 7.0
    VAL_MAX_TEMP = 31.0
    VAL_OPEN_POSITION = 0
    VAL_CLOSE_POSITION = 100
    VAL_OPEN_TILT = 100
    VAL_CLOSE_TILT = 0
    VAL_FACTOR: int | None = None
