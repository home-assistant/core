"""Provides the constants needed for component."""

# All activity disabled / Device is off/standby
HUMIDIFIER_MODE_OFF = "off"

# The device supports humidifying/drying to a range
HUMIDIFIER_MODE_HUMIDIFY_DRY = "humidify_dry"

# The humidity is set based on a schedule, learned behavior, AI or some
# other related mechanism. User is not able to adjust the humidity
HUMIDIFIER_MODE_AUTO = "auto"

# Device is in Dry mode
HUMIDIFIER_MODE_DRY = "dry"

# Device is in Humidification/Misting mode
HUMIDIFIER_MODE_HUMIDIFY = "humidify"

# Only the fan is on, not fan and another mode like humidify
HUMIDIFIER_MODE_FAN_ONLY = "fan_only"

HUMIDIFIER_MODES = [
    HUMIDIFIER_MODE_OFF,
    HUMIDIFIER_MODE_HUMIDIFY_DRY,
    HUMIDIFIER_MODE_AUTO,
    HUMIDIFIER_MODE_DRY,
    HUMIDIFIER_MODE_HUMIDIFY,
    HUMIDIFIER_MODE_FAN_ONLY,
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

# Device is reacting to activity (e.g. movement sensors)
PRESET_ACTIVITY = "activity"


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
ATTR_FAN_MODES = "fan_modes"
ATTR_FAN_MODE = "fan_mode"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_HUMIDIFIER_ACTIONS = "humidifier_action"
ATTR_HUMIDIFIER_MODES = "humidifier_modes"
ATTR_HUMIDIFIER_MODE = "humidifier_mode"

DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

DOMAIN = "humidifier"

SERVICE_SET_PRESET_MODE = "set_preset_mode"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_HUMIDITY = "set_humidity"
SERVICE_SET_HUMIDIFIER_MODE = "set_humidifier_mode"

SUPPORT_TARGET_HUMIDITY = 1
SUPPORT_PRESET_MODE = 2
SUPPORT_FAN_MODE = 4
