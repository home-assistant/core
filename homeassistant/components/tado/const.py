"""Constant values for the Tado component."""

from PyTado.const import (
    CONST_HVAC_COOL,
    CONST_HVAC_DRY,
    CONST_HVAC_FAN,
    CONST_HVAC_HEAT,
    CONST_HVAC_HOT_WATER,
    CONST_HVAC_IDLE,
    CONST_HVAC_OFF,
)

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SWING_OFF,
    SWING_ON,
    HVACAction,
    HVACMode,
)

TADO_HVAC_ACTION_TO_HA_HVAC_ACTION = {
    CONST_HVAC_HEAT: HVACAction.HEATING,
    CONST_HVAC_DRY: HVACAction.DRYING,
    CONST_HVAC_FAN: HVACAction.FAN,
    CONST_HVAC_COOL: HVACAction.COOLING,
    CONST_HVAC_IDLE: HVACAction.IDLE,
    CONST_HVAC_OFF: HVACAction.OFF,
    CONST_HVAC_HOT_WATER: HVACAction.HEATING,
}

# Configuration
CONF_FALLBACK = "fallback"
CONF_HOME_ID = "home_id"
DATA = "data"
UPDATE_TRACK = "update_track"
UPDATE_MOBILE_DEVICE_TRACK = "update_mobile_device_track"

# Weather
CONDITIONS_MAP = {
    "clear-night": {"NIGHT_CLEAR"},
    "cloudy": {"CLOUDY", "CLOUDY_MOSTLY", "NIGHT_CLOUDY"},
    "fog": {"FOGGY"},
    "hail": {"HAIL", "RAIN_HAIL"},
    "lightning": {"THUNDERSTORM"},
    "partlycloudy": {"CLOUDY_PARTLY"},
    "rainy": {"DRIZZLE", "RAIN", "SCATTERED_RAIN"},
    "snowy": {"FREEZING", "SCATTERED_SNOW", "SNOW"},
    "snowy-rainy": {"RAIN_SNOW", "SCATTERED_RAIN_SNOW"},
    "sunny": {"SUN"},
    "windy": {"WIND"},
}

# Types
TYPE_AIR_CONDITIONING = "AIR_CONDITIONING"
TYPE_HEATING = "HEATING"
TYPE_HOT_WATER = "HOT_WATER"

TYPE_BATTERY = "BATTERY"
TYPE_POWER = "POWER"

# Base modes
CONST_MODE_OFF = "OFF"
CONST_MODE_SMART_SCHEDULE = "SMART_SCHEDULE"  # Use the schedule
CONST_MODE_AUTO = "AUTO"
CONST_MODE_COOL = "COOL"
CONST_MODE_HEAT = "HEAT"
CONST_MODE_DRY = "DRY"
CONST_MODE_FAN = "FAN"

CONST_LINK_OFFLINE = "OFFLINE"

CONST_FAN_OFF = "OFF"
CONST_FAN_AUTO = "AUTO"
CONST_FAN_LOW = "LOW"
CONST_FAN_MIDDLE = "MIDDLE"
CONST_FAN_HIGH = "HIGH"


# When we change the temperature setting, we need an overlay mode
CONST_OVERLAY_TADO_MODE = (
    "NEXT_TIME_BLOCK"  # wait until tado changes the mode automatic
)
CONST_OVERLAY_MANUAL = "MANUAL"  # the user has change the temperature or mode manually
CONST_OVERLAY_TIMER = "TIMER"  # the temperature will be reset after a timespan
CONST_OVERLAY_TADO_DEFAULT = (
    "TADO_DEFAULT"  # use the setting from tado zone itself (set in Tado app or webapp)
)
CONST_OVERLAY_TADO_OPTIONS = [
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
]
CONST_EXCLUSIVE_OVERLAY_GROUP = (
    "overlay_group"  # Overlay group for set_climate_timer service
)


# Heat always comes first since we get the
# min and max temperatures for the zone from
# it.
# Heat is preferred as it generally has a lower minimum temperature
ORDERED_KNOWN_TADO_MODES = [
    CONST_MODE_HEAT,
    CONST_MODE_COOL,
    CONST_MODE_AUTO,
    CONST_MODE_DRY,
    CONST_MODE_FAN,
]

TADO_MODES_TO_HA_CURRENT_HVAC_ACTION = {
    CONST_MODE_HEAT: HVACAction.HEATING,
    CONST_MODE_DRY: HVACAction.DRYING,
    CONST_MODE_FAN: HVACAction.FAN,
    CONST_MODE_COOL: HVACAction.COOLING,
}

# These modes will not allow a temp to be set
TADO_MODES_WITH_NO_TEMP_SETTING = [CONST_MODE_AUTO, CONST_MODE_FAN]
#
# HVAC_MODE_HEAT_COOL is mapped to CONST_MODE_AUTO
#    This lets tado decide on a temp
#
# HVAC_MODE_AUTO is mapped to CONST_MODE_SMART_SCHEDULE
#    This runs the smart schedule
#
HA_TO_TADO_HVAC_MODE_MAP = {
    HVACMode.OFF: CONST_MODE_OFF,
    HVACMode.HEAT_COOL: CONST_MODE_AUTO,
    HVACMode.AUTO: CONST_MODE_SMART_SCHEDULE,
    HVACMode.HEAT: CONST_MODE_HEAT,
    HVACMode.COOL: CONST_MODE_COOL,
    HVACMode.DRY: CONST_MODE_DRY,
    HVACMode.FAN_ONLY: CONST_MODE_FAN,
}

HA_TO_TADO_FAN_MODE_MAP = {
    FAN_AUTO: CONST_FAN_AUTO,
    FAN_OFF: CONST_FAN_OFF,
    FAN_LOW: CONST_FAN_LOW,
    FAN_MEDIUM: CONST_FAN_MIDDLE,
    FAN_HIGH: CONST_FAN_HIGH,
}

TADO_TO_HA_HVAC_MODE_MAP = {
    value: key for key, value in HA_TO_TADO_HVAC_MODE_MAP.items()
}

TADO_TO_HA_FAN_MODE_MAP = {value: key for key, value in HA_TO_TADO_FAN_MODE_MAP.items()}

DEFAULT_TADO_PRECISION = 0.1

# Constant for Auto Geolocation mode
PRESET_AUTO = "auto"

SUPPORT_PRESET_AUTO = [PRESET_AWAY, PRESET_HOME, PRESET_AUTO]
SUPPORT_PRESET_MANUAL = [PRESET_AWAY, PRESET_HOME]

SENSOR_DATA_CATEGORY_WEATHER = "weather"
SENSOR_DATA_CATEGORY_GEOFENCE = "geofence"

TADO_SWING_OFF = "OFF"
TADO_SWING_ON = "ON"

HA_TO_TADO_SWING_MODE_MAP = {
    SWING_OFF: TADO_SWING_OFF,
    SWING_ON: TADO_SWING_ON,
}

TADO_TO_HA_SWING_MODE_MAP = {
    value: key for key, value in HA_TO_TADO_SWING_MODE_MAP.items()
}

DOMAIN = "tado"

SIGNAL_TADO_UPDATE_RECEIVED = "tado_update_received_{}_{}_{}"
SIGNAL_TADO_MOBILE_DEVICE_UPDATE_RECEIVED = "tado_mobile_device_update_received_{}"
UNIQUE_ID = "unique_id"

DEFAULT_NAME = "Tado"

TADO_HOME = "Home"
TADO_ZONE = "Zone"

UPDATE_LISTENER = "update_listener"

# Constants for Temperature Offset
INSIDE_TEMPERATURE_MEASUREMENT = "INSIDE_TEMPERATURE_MEASUREMENT"
TEMP_OFFSET = "temperatureOffset"
TADO_OFFSET_CELSIUS = "celsius"
HA_OFFSET_CELSIUS = "offset_celsius"
TADO_OFFSET_FAHRENHEIT = "fahrenheit"
HA_OFFSET_FAHRENHEIT = "offset_fahrenheit"
TADO_TO_HA_OFFSET_MAP = {
    TADO_OFFSET_CELSIUS: HA_OFFSET_CELSIUS,
    TADO_OFFSET_FAHRENHEIT: HA_OFFSET_FAHRENHEIT,
}

# Constants for Overlay Default settings
HA_TERMINATION_TYPE = "default_overlay_type"
HA_TERMINATION_DURATION = "default_overlay_seconds"

TADO_DEFAULT_MIN_TEMP = 5
TADO_DEFAULT_MAX_TEMP = 25
# Constants for service calls
SERVICE_ADD_METER_READING = "add_meter_reading"
CONF_CONFIG_ENTRY = "config_entry"
CONF_READING = "reading"
ATTR_MESSAGE = "message"
