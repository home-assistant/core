"""Provides the constants needed for component."""

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


ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"

DEFAULT_MIN_HUMIDITY = 0
DEFAULT_MAX_HUMIDITY = 100

DOMAIN = "humidifier"

SERVICE_SET_PRESET_MODE = "set_preset_mode"
SERVICE_SET_HUMIDITY = "set_humidity"

SUPPORT_PRESET_MODE = 1
