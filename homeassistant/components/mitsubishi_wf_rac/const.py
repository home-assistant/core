"""Constants used by the mitsubishi-wf-rac component."""

from datetime import timedelta

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntityFeature,
    HVACMode,
)

DOMAIN = "mitsubishi_wf_rac"

# The module serves its API here on every firmware branch, and the port cannot
# be changed on the device - only the scheme differs (plain http on the older
# WF-RAC branch). Used as the manual-setup default and as the fallback when a
# discovery announcement carries something else.
DEFAULT_PORT = 51443

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONF_OPERATOR_ID = "operator_id"
CONF_AIRCO_ID = "airco_id"
# Removed option, kept only so async_migrate_entry can strip it from entries
# that predate v5. Nothing outside the migration reads it.
CONF_AVAILABILITY_CHECK = "availability_check"
# Consecutive failed polls before the device is reported unavailable; floored
# at coordinator.py's AVAILABILITY_FAILURE_LIMIT_MIN.
CONF_AVAILABILITY_RETRY_LIMIT = "availability_retry_limit"
CONF_CONNECTION_METHOD = "connection_method"


# New offset constants
CONF_INDOOR_OFFSET = "indoor_offset"
CONF_OUTDOOR_OFFSET = "outdoor_offset"
CONF_TARGET_OFFSET = "target_offset"
CONF_TARGET_OFFSET_COOL = "target_offset_cool"
CONF_TARGET_OFFSET_HEAT = "target_offset_heat"


# Heating uses the unit's own Heating TempSetting (10.0°C), which matches
# HOME_LEAVE_TEMP_HEAT exactly. Cooling does not: the unit's Cooling
# TempSetting reads 33.0°C, but the temperature actually applied while the
# official app's away-cool mode is running is 31.0°C - so this hardcodes the
# applied value rather than trusting the configured TempSetting, since only
# the applied value is known to flip Vacant.
HOME_LEAVE_TEMP_HEAT = 10.0
HOME_LEAVE_TEMP_COOL = 31.0
# Temperature to restore when leaving Home Leave mode. There's no reliable way
# to recall whatever temperature was set before Home Leave was turned on (the
# unit itself doesn't report it), so this is a plain, reasonable default.
NORMAL_TEMP = 21.0


SUPPORT_FLAGS = (
    ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_HORIZONTAL_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

SUPPORTED_HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
]

HVAC_TRANSLATION = {
    HVACMode.AUTO: 0,
    HVACMode.COOL: 1,
    HVACMode.HEAT: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.DRY: 4,
}

SWING_3D_AUTO = "3d_auto"
SWING_VERTICAL_POSITION_1 = "highest"
SWING_VERTICAL_POSITION_2 = "middle"
SWING_VERTICAL_POSITION_3 = "normal"
SWING_VERTICAL_POSITION_4 = "lowest"
SWING_VERTICAL_AUTO = "up_down_auto"

SWING_HORIZONTAL_POSITION_1 = "left_left"
SWING_HORIZONTAL_POSITION_2 = "left_center"
SWING_HORIZONTAL_POSITION_3 = "center_center"
SWING_HORIZONTAL_POSITION_4 = "center_right"
SWING_HORIZONTAL_POSITION_5 = "right_right"
SWING_HORIZONTAL_POSITION_6 = "left_right"
SWING_HORIZONTAL_POSITION_7 = "right_left"
SWING_HORIZONTAL_AUTO = "left_right_auto"


SWING_MODE_TRANSLATION = {
    SWING_VERTICAL_AUTO: 0,
    SWING_VERTICAL_POSITION_1: 1,
    SWING_VERTICAL_POSITION_2: 2,
    SWING_VERTICAL_POSITION_3: 3,
    SWING_VERTICAL_POSITION_4: 4,
}

SUPPORT_SWING_MODES = [
    SWING_VERTICAL_AUTO,
    SWING_VERTICAL_POSITION_1,
    SWING_VERTICAL_POSITION_2,
    SWING_VERTICAL_POSITION_3,
    SWING_VERTICAL_POSITION_4,
    SWING_3D_AUTO,
]

SWING_HORIZONTAL_MODE_TRANSLATION = {
    SWING_HORIZONTAL_AUTO: 0,
    SWING_HORIZONTAL_POSITION_1: 1,
    SWING_HORIZONTAL_POSITION_2: 2,
    SWING_HORIZONTAL_POSITION_3: 3,
    SWING_HORIZONTAL_POSITION_4: 4,
    SWING_HORIZONTAL_POSITION_5: 5,
    SWING_HORIZONTAL_POSITION_6: 6,
    SWING_HORIZONTAL_POSITION_7: 7,
}

SUPPORT_SWING_HORIZONTAL_MODES = [
    SWING_HORIZONTAL_AUTO,
    SWING_HORIZONTAL_POSITION_1,
    SWING_HORIZONTAL_POSITION_2,
    SWING_HORIZONTAL_POSITION_3,
    SWING_HORIZONTAL_POSITION_4,
    SWING_HORIZONTAL_POSITION_5,
    SWING_HORIZONTAL_POSITION_6,
    SWING_HORIZONTAL_POSITION_7,
    SWING_3D_AUTO,
]


FAN_QUIET = "quiet"

FAN_MODE_TRANSLATION = {
    FAN_AUTO: 0,
    FAN_QUIET: 1,
    FAN_LOW: 2,
    FAN_MEDIUM: 3,
    FAN_HIGH: 4,
}

SUPPORTED_FAN_MODES = [
    FAN_AUTO,
    FAN_QUIET,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
]


# Optional certificate for the unit's HTTPS stack, looked up in the HA config
# directory. Without it the connection falls back to a permissive SSL context.
# Create it by running this in that directory:
#   openssl s_client -connect <AC_IP_ADDRESS>:51443 -showcerts </dev/null 2>/dev/null \
#       | openssl x509 -outform PEM > ac_cert.pem
AC_CERT_FILENAME = "ac_cert.pem"
