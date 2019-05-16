"""Provides the constants needed for component."""

# All activity disabled / Device is off/standby
OPERATION_MODE_OFF = 'off'

# Heating
OPERATION_MODE_HEAT = 'heat'

# Cooling
OPERATION_MODE_COOL = 'cool'

# The device supports heating/cooling to a range
OPERATION_MODE_HEATCOOL = 'heatcool'

# The temperature is set based on a schedule, learned behavior, AI or some
# other related mechanism. User is not able to adjust the temperature
OPERATION_MODE_AUTO = 'auto'

# Device is in Dry/Huminity mode
OPERATION_MODE_DRY = 'dry'

# Only the fan is on, not fan and another mode like cool
OPERATION_MODE_FAN_ONLY = 'fan_only'

OPERATION_MODES = [
    OPERATION_MODE_OFF,
    OPERATION_MODE_HEAT,
    OPERATION_MODE_COOL,
    OPERATION_MODE_HEATCOOL,
    OPERATION_MODE_AUTO,
    OPERATION_MODE_DRY,
    OPERATION_MODE_FAN_ONLY,
]


# Device is running an energy-saving mode
HOLD_MODE_ECO = 'eco'

# Device is on away mode
HOLD_MODE_AWAY = 'away'

# Device turn all valve full up
HOLD_MODE_BOOST = 'boost'


# This are support current states of HVAC
OPERATION_CURRENT_OFF = 'off'
OPERATION_CURRENT_HEAT = 'heat'
OPERATION_CURRENT_COOL = 'cool'
OPERATION_CURRENT_DRY = 'dry'
OPERATION_CURRENT_IDLE = 'idle'
OPERATION_CURRENT_FAN_ONLY = 'fan_only'


ATTR_AUX_HEAT = 'aux_heat'
ATTR_CURRENT_HUMIDITY = 'current_humidity'
ATTR_CURRENT_TEMPERATURE = 'current_temperature'
ATTR_FAN_LIST = 'fan_list'
ATTR_FAN_MODE = 'fan_mode'
ATTR_HOLD_MODE = 'hold_mode'
ATTR_HOLD_LIST = 'hold_list'
ATTR_HUMIDITY = 'humidity'
ATTR_MAX_HUMIDITY = 'max_humidity'
ATTR_MIN_HUMIDITY = 'min_humidity'
ATTR_MAX_TEMP = 'max_temp'
ATTR_MIN_TEMP = 'min_temp'
ATTR_OPERATION_LIST = 'operation_list'
ATTR_OPERATION_MODE = 'operation_mode'
ATTR_OPERATION_CURRENT = 'operation_current'
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
SERVICE_SET_HOLD_MODE = 'set_hold_mode'
SERVICE_SET_HUMIDITY = 'set_humidity'
SERVICE_SET_OPERATION_MODE = 'set_operation_mode'
SERVICE_SET_SWING_MODE = 'set_swing_mode'
SERVICE_SET_TEMPERATURE = 'set_temperature'

SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_TARGET_TEMPERATURE_HIGH = 2
SUPPORT_TARGET_TEMPERATURE_LOW = 4
SUPPORT_TARGET_HUMIDITY = 8
SUPPORT_TARGET_HUMIDITY_HIGH = 16
SUPPORT_TARGET_HUMIDITY_LOW = 32
SUPPORT_FAN_MODE = 64
SUPPORT_HOLD_MODE = 128
SUPPORT_SWING_MODE = 256
SUPPORT_AUX_HEAT = 512
SUPPORT_ON_OFF = 1024
SUPPORT_CURRENT_OPERATION = 2048
