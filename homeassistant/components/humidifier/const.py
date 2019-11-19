"""Provides the constants needed for component."""

# All activity disabled / Device is off/standby
OPERATION_MODE_OFF = "off"

# The device supports humidifying/drying to a range
OPERATION_MODE_HUMIDIFY_DRY = "humidify_dry"

# The humidity is set based on a schedule, learned behavior, AI or some
# other related mechanism. User is not able to adjust the target humidity
OPERATION_MODE_AUTO = "auto"

# Device is in Dry mode
OPERATION_MODE_DRY = "dry"

# Device is in Humidification/Misting mode
OPERATION_MODE_HUMIDIFY = "humidify"

# Only the fan is on, not fan and another mode like humidify
OPERATION_MODE_FAN_ONLY = "fan_only"

OPERATION_MODES = [
    OPERATION_MODE_OFF,
    OPERATION_MODE_HUMIDIFY_DRY,
    OPERATION_MODE_AUTO,
    OPERATION_MODE_DRY,
    OPERATION_MODE_HUMIDIFY,
    OPERATION_MODE_FAN_ONLY,
]

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


# Possible fan state
FAN_ON = "on"
FAN_OFF = "off"
FAN_AUTO = "auto"
FAN_LOW = "low"
FAN_MEDIUM = "medium"
FAN_HIGH = "high"
FAN_MIDDLE = "middle"
FAN_FOCUS = "focus"
FAN_DIFFUSE = "diffuse"


# This are support current states of HUMIDIFIER
CURRENT_HUMIDIFIER_OFF = "off"
CURRENT_HUMIDIFIER_DRY = "drying"
CURRENT_HUMIDIFIER_HUMIDIFY = "humidifying"
CURRENT_HUMIDIFIER_IDLE = "idle"
CURRENT_HUMIDIFIER_FAN = "fan"


ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_FAN_MODES = "fan_modes"
ATTR_FAN_MODE = "fan_mode"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_HUMIDIFIER_ACTION = "humidifier_action"
ATTR_OPERATION_MODES = "operation_modes"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_WATER_LEVEL = "water_level"

DEFAULT_MIN_HUMIDITY = 0
DEFAULT_MAX_HUMIDITY = 100

DOMAIN = "humidifier"

SERVICE_SET_PRESET_MODE = "set_preset_mode"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_HUMIDITY = "set_humidity"
SERVICE_SET_OPERATION_MODE = "set_operation_mode"

SUPPORT_TARGET_HUMIDITY = 1
SUPPORT_PRESET_MODE = 2
SUPPORT_FAN_MODE = 4
SUPPORT_TEMPERATURE = 8
SUPPORT_WATER_LEVEL = 16
