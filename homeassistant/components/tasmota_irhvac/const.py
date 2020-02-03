"""Provides the constants needed for component."""

# All activity disabled / Device is off/standby
HVAC_MODE_OFF = "off"

# Heating
HVAC_MODE_HEAT = "heat"

# Cooling
HVAC_MODE_COOL = "cool"

# The device supports heating/cooling to a range
HVAC_MODE_HEAT_COOL = "heat_cool"

# The temperature is set based on a schedule, learned behavior, AI or some
# other related mechanism. User is not able to adjust the temperature
HVAC_MODE_AUTO = "auto"

# Device is in Dry/Humidity mode
HVAC_MODE_DRY = "dry"

# Only the fan is on, not fan and another mode like cool
HVAC_MODE_FAN_ONLY = "fan_only"

# Some devices have "auto" and "fan_only" changed
HVAC_MODE_AUTO_FAN = "auto_fan_only"

# Some devicec have "fan_only" and "auto" changed
HVAC_MODE_FAN_AUTO = "fan_only_auto"

HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_AUTO,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_AUTO_FAN,
    HVAC_MODE_FAN_AUTO,
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

HVAC_FAN_MIN = "min"
HVAC_FAN_MEDIUM = "medium"
HVAC_FAN_MAX = "max"
HVAC_FAN_AUTO = "auto"

# Some devices say max,but it is high, and auto which is max
HVAC_FAN_MAX_HIGH = "max_high"
HVAC_FAN_AUTO_MAX = "auto_max"


# Possible swing state
SWING_OFF = "off"
SWING_BOTH = "both"
SWING_VERTICAL = "vertical"
SWING_HORIZONTAL = "horizontal"


# This are support current states of HVAC
CURRENT_HVAC_OFF = "off"
CURRENT_HVAC_HEAT = "heating"
CURRENT_HVAC_COOL = "cooling"
CURRENT_HVAC_DRY = "drying"
CURRENT_HVAC_IDLE = "idle"
CURRENT_HVAC_FAN = "fan"
CURRENT_HVAC_AUTO = "auto"


# #### STATES ####
STATE_ON = "on"
STATE_OFF = "off"
STATE_UNKNOWN = "unknown"
STATE_HEAT = "heat"
STATE_COOL = "cool"
STATE_IDLE = "idle"
STATE_AUTO = "auto"
STATE_MANUAL = "manual"
STATE_DRY = "dry"
STATE_FAN_ONLY = "fan_only"
STATE_ECO = "eco"


# Contains one string or a list of strings, each being an entity id
ATTR_ENTITY_ID = "entity_id"

# Contains one string or a list of strings, each being an area id
ATTR_AREA_ID = "area_id"


ATTR_AWAY_MODE = "away_mode"
ATTR_AUX_HEAT = "aux_heat"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_FAN_MODES = "fan_modes"
ATTR_FAN_MODE = "fan_mode"
ATTR_FAN_LIST = "fan_list"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"
ATTR_HUMIDITY = "humidity"
ATTR_MAX_HUMIDITY = "max_humidity"
ATTR_MIN_HUMIDITY = "min_humidity"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_HOLD_MODE = "hold_mode"
ATTR_HVAC_ACTIONS = "hvac_action"
ATTR_HVAC_ACTION = "hvac_action"
ATTR_HVAC_MODES = "hvac_modes"
ATTR_HVAC_MODE = "hvac_mode"
ATTR_SWING_MODES = "swing_modes"
ATTR_SWING_MODE = "swing_mode"
ATTR_SWING_LIST = "swing_list"
ATTR_TEMPERATURE = "temperature"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_TARGET_TEMP_STEP = "target_temp_step"
ATTR_OPERATION_LIST = "operation_list"
ATTR_OPERATION_MODE = "operation_mode"

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

DOMAIN = "climate"
CONF_NAME = "name"
CONF_PLATFORM = "platform"

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_AUX_HEAT = "set_aux_heat"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_PRESET_MODE = "set_preset_mode"
SERVICE_SET_HUMIDITY = "set_humidity"
SERVICE_SET_HVAC_MODE = "set_hvac_mode"
SERVICE_SET_SWING_MODE = "set_swing_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_HOLD_MODE = "set_hold_mode"
SERVICE_SET_OPERATION_MODE = "set_operation_mode"
SERVICE_TURN_ON = "turn_on"
SERVICE_TURN_OFF = "turn_off"

SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_TARGET_TEMPERATURE_RANGE = 2
SUPPORT_PRESET_MODE = 16
SUPPORT_TARGET_TEMPERATURE_HIGH = 2
SUPPORT_TARGET_TEMPERATURE_LOW = 4
SUPPORT_TARGET_HUMIDITY = 4
SUPPORT_TARGET_HUMIDITY_HIGH = 16
SUPPORT_TARGET_HUMIDITY_LOW = 32
SUPPORT_FAN_MODE = 8
SUPPORT_OPERATION_MODE = 128
SUPPORT_HOLD_MODE = 256
SUPPORT_SWING_MODE = 32
SUPPORT_AWAY_MODE = 1024
SUPPORT_AUX_HEAT = 64
SUPPORT_ON_OFF = 4096

# The degree of precision for platforms
PRECISION_WHOLE = 1
PRECISION_HALVES = 0.5
PRECISION_TENTHS = 0.1

EVENT_HOMEASSISTANT_START = "homeassistant_start"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENTITY_NAMESPACE = "entity_namespace"

# Temperature units
TEMP_CELSIUS = "°C"
TEMP_FAHRENHEIT = "°F"
