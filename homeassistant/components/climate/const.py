"""Provides the constants needed for component."""

# All activity disabled / Device is off/standby
HVAC_MODE_OFF = 'off'

# Heating
HVAC_MODE_HEAT = 'heat'

# Cooling
HVAC_MODE_COOL = 'cool'

# The device supports heating/cooling to a range
HVAC_MODE_HEAT_COOL = 'heat_cool'

# The temperature is set based on a schedule, learned behavior, AI or some
# other related mechanism. User is not able to adjust the temperature
HVAC_MODE_AUTO = 'auto'

# Device is in Dry/Humidity mode
HVAC_MODE_DRY = 'dry'

# Only the fan is on, not fan and another mode like cool
HVAC_MODE_FAN_ONLY = 'fan_only'

HVAC_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_AUTO,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
]


# Device is running an energy-saving mode
PRESET_ECO = 'eco'

# Device is on away mode
PRESET_AWAY = 'away'

# Device turn all valve full up
PRESET_BOOST = 'boost'

# Device have a comfort mode
PRESET_COMFORT = 'comfort'

# Device is on home mode
PRESET_HOME = 'home'

# Device is prepared for sleep
PRESET_SLEEP = 'sleep'


# Possible fan state
FAN_ON = "on"
FAN_OFF = "off"
FAN_AUTO = "auto"
FAN_LOW = "low"
FAN_MEDIUM = "medium"
FAN_HIGH = "high"
FAN_FOCUS = "focus"
FAN_DIFFUSE = "diffuse"


# This are support current states of HVAC
CURRENT_HVAC_OFF = 'off'
CURRENT_HVAC_HEAT = 'heating'
CURRENT_HVAC_COOL = 'cooling'
CURRENT_HVAC_DRY = 'drying'
CURRENT_HVAC_IDLE = 'idle'


ATTR_AUX_HEAT = 'aux_heat'
ATTR_CURRENT_HUMIDITY = 'current_humidity'
ATTR_CURRENT_TEMPERATURE = 'current_temperature'
ATTR_CURRENT_HVAC = 'current_hvac'
ATTR_FAN_LIST = 'fan_list'
ATTR_FAN_MODE = 'fan_mode'
ATTR_PRESET_MODE = 'preset_mode'
ATTR_PRESET_LIST = 'preset_list'
ATTR_HUMIDITY = 'humidity'
ATTR_MAX_HUMIDITY = 'max_humidity'
ATTR_MIN_HUMIDITY = 'min_humidity'
ATTR_MAX_TEMP = 'max_temp'
ATTR_MIN_TEMP = 'min_temp'
ATTR_HVAC_MODES = 'hvac_modes'
ATTR_HVAC_MODE = 'hvac_mode'
ATTR_SWING_LIST = 'swing_list'
ATTR_SWING_MODE = 'swing_mode'
ATTR_TARGET_TEMP_HIGH = 'target_temp_high'
ATTR_TARGET_TEMP_LOW = 'target_temp_low'
ATTR_TARGET_TEMP_STEP = 'target_temp_step'

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35
DEFAULT_MIN_HUMITIDY = 30
DEFAULT_MAX_HUMIDITY = 99

DOMAIN = 'climate'

SERVICE_SET_AUX_HEAT = 'set_aux_heat'
SERVICE_SET_FAN_MODE = 'set_fan_mode'
SERVICE_SET_PRESET_MODE = 'set_preset_mode'
SERVICE_SET_HUMIDITY = 'set_humidity'
SERVICE_SET_HVAC_MODE = 'set_hvac_mode'
SERVICE_SET_SWING_MODE = 'set_swing_mode'
SERVICE_SET_TEMPERATURE = 'set_temperature'

SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_TARGET_TEMPERATURE_RANGE = 2
SUPPORT_TARGET_HUMIDITY = 4
SUPPORT_FAN_MODE = 8
SUPPORT_PRESET_MODE = 16
SUPPORT_SWING_MODE = 32
SUPPORT_AUX_HEAT = 64
SUPPORT_CURRENT_HVAC = 128
