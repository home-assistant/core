"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum


class HVACMode(StrEnum):
    """HVAC mode for climate devices."""

    # All activity disabled / Device is off/standby
    OFF = "off"

    # Heating
    HEAT = "heat"

    # Cooling
    COOL = "cool"

    # The device supports heating/cooling to a range
    HEAT_COOL = "heat_cool"

    # The temperature is set based on a schedule, learned behavior, AI or some
    # other related mechanism. User is not able to adjust the temperature
    AUTO = "auto"

    # Device is in Dry/Humidity mode
    DRY = "dry"

    # Only the fan is on, not fan and another mode like cool
    FAN_ONLY = "fan_only"


HVAC_MODES = [cls.value for cls in HVACMode]

# No preset is active
PRESET_NONE = "none"

# Device is running an energy-saving mode
PRESET_ECO = "eco"

# Device is in away mode
PRESET_AWAY = "away"

# Device turn all valve full up
PRESET_BOOST = "boost"

# Device is in comfort mode
PRESET_COMFORT = "comfort"

# Device is in home mode
PRESET_HOME = "home"

# Device is prepared for sleep
PRESET_SLEEP = "sleep"

# Device is reacting to activity (e.g. movement sensors)
PRESET_ACTIVITY = "activity"

# Possible fan state
FAN_ON = "on"
FAN_OFF = "off"
FAN_AUTO = "auto"
FAN_LOW = "low"
FAN_MEDIUM = "medium"
FAN_HIGH = "high"
FAN_TOP = "top"
FAN_MIDDLE = "middle"
FAN_FOCUS = "focus"
FAN_DIFFUSE = "diffuse"


# Possible swing state
SWING_ON = "on"
SWING_OFF = "off"
SWING_BOTH = "both"
SWING_VERTICAL = "vertical"
SWING_HORIZONTAL = "horizontal"

# Possible horizontal swing state
SWING_HORIZONTAL_ON = "on"
SWING_HORIZONTAL_OFF = "off"


class HVACAction(StrEnum):
    """HVAC action for climate devices."""

    COOLING = "cooling"
    DEFROSTING = "defrosting"
    DRYING = "drying"
    FAN = "fan"
    HEATING = "heating"
    IDLE = "idle"
    OFF = "off"
    PREHEATING = "preheating"


CURRENT_HVAC_ACTIONS = [cls.value for cls in HVACAction]


ATTR_AUX_HEAT = "aux_heat"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_FAN_MODES = "fan_modes"
ATTR_FAN_MODE = "fan_mode"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_HVAC_ACTION = "hvac_action"
ATTR_HVAC_MODES = "hvac_modes"
ATTR_HVAC_MODE = "hvac_mode"
ATTR_SWING_MODES = "swing_modes"
ATTR_SWING_MODE = "swing_mode"
ATTR_SWING_HORIZONTAL_MODE = "swing_horizontal_mode"
ATTR_SWING_HORIZONTAL_MODES = "swing_horizontal_modes"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_TARGET_TEMP_STEP = "target_temp_step"

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

DOMAIN = "climate"

INTENT_GET_TEMPERATURE = "HassClimateGetTemperature"

SERVICE_SET_AUX_HEAT = "set_aux_heat"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_PRESET_MODE = "set_preset_mode"
SERVICE_SET_HUMIDITY = "set_humidity"
SERVICE_SET_HVAC_MODE = "set_hvac_mode"
SERVICE_SET_SWING_MODE = "set_swing_mode"
SERVICE_SET_SWING_HORIZONTAL_MODE = "set_swing_horizontal_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"


class ClimateEntityFeature(IntFlag):
    """Supported features of the climate entity."""

    TARGET_TEMPERATURE = 1
    TARGET_TEMPERATURE_RANGE = 2
    TARGET_HUMIDITY = 4
    FAN_MODE = 8
    PRESET_MODE = 16
    SWING_MODE = 32
    AUX_HEAT = 64
    TURN_OFF = 128
    TURN_ON = 256
    SWING_HORIZONTAL_MODE = 512
