"""Constants for the Mitsubishi WF-RAC integration."""

from datetime import timedelta

from pywfrac import AirFlow, OperationMode, WindDirectionLR, WindDirectionUD

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntityFeature,
    HVACMode,
)

DOMAIN = "mitsubishi_wf_rac"

# Fixed on every firmware branch; only the scheme differs.
DEFAULT_PORT = 51443

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONF_OPERATOR_ID = "operator_id"
CONF_AIRCO_ID = "airco_id"
# Removed option, kept so async_migrate_entry can strip it.
CONF_AVAILABILITY_CHECK = "availability_check"
# Removed option, kept so async_migrate_entry can strip it.
CONF_AVAILABILITY_RETRY_LIMIT = "availability_retry_limit"
CONF_CONNECTION_METHOD = "connection_method"


# The unit's own cooling Home Leave default is 33 °C, but only 31 °C sets Vacant.
HOME_LEAVE_TEMP_HEAT = 10.0
HOME_LEAVE_TEMP_COOL = 31.0
# The unit does not report the setpoint from before Home Leave.
NORMAL_TEMP = 21.0


# Horizontal swing and the away preset depend on the unit's capabilities.
SUPPORT_FLAGS = (
    ClimateEntityFeature.FAN_MODE
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
    HVACMode.AUTO: OperationMode.AUTO,
    HVACMode.COOL: OperationMode.COOL,
    HVACMode.HEAT: OperationMode.HEAT,
    HVACMode.FAN_ONLY: OperationMode.FAN,
    HVACMode.DRY: OperationMode.DRY,
}
HVAC_MODE_BY_OPERATION = {mode: hvac for hvac, mode in HVAC_TRANSLATION.items()}

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
    SWING_VERTICAL_AUTO: WindDirectionUD.AUTO,
    SWING_VERTICAL_POSITION_1: WindDirectionUD.POSITION_1,
    SWING_VERTICAL_POSITION_2: WindDirectionUD.POSITION_2,
    SWING_VERTICAL_POSITION_3: WindDirectionUD.POSITION_3,
    SWING_VERTICAL_POSITION_4: WindDirectionUD.POSITION_4,
}
SWING_MODE_BY_DIRECTION = {mode: name for name, mode in SWING_MODE_TRANSLATION.items()}

SUPPORT_SWING_MODES = [
    SWING_VERTICAL_AUTO,
    SWING_VERTICAL_POSITION_1,
    SWING_VERTICAL_POSITION_2,
    SWING_VERTICAL_POSITION_3,
    SWING_VERTICAL_POSITION_4,
    SWING_3D_AUTO,
]

SWING_HORIZONTAL_MODE_TRANSLATION = {
    SWING_HORIZONTAL_AUTO: WindDirectionLR.AUTO,
    SWING_HORIZONTAL_POSITION_1: WindDirectionLR.POSITION_1,
    SWING_HORIZONTAL_POSITION_2: WindDirectionLR.POSITION_2,
    SWING_HORIZONTAL_POSITION_3: WindDirectionLR.POSITION_3,
    SWING_HORIZONTAL_POSITION_4: WindDirectionLR.POSITION_4,
    SWING_HORIZONTAL_POSITION_5: WindDirectionLR.POSITION_5,
    SWING_HORIZONTAL_POSITION_6: WindDirectionLR.POSITION_6,
    SWING_HORIZONTAL_POSITION_7: WindDirectionLR.POSITION_7,
}

SWING_HORIZONTAL_MODE_BY_DIRECTION = {
    mode: name for name, mode in SWING_HORIZONTAL_MODE_TRANSLATION.items()
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
]


FAN_QUIET = "quiet"

FAN_MODE_TRANSLATION = {
    FAN_AUTO: AirFlow.AUTO,
    FAN_QUIET: AirFlow.QUIET,
    FAN_LOW: AirFlow.LOW,
    FAN_MEDIUM: AirFlow.MEDIUM,
    FAN_HIGH: AirFlow.HIGH,
}
FAN_MODE_BY_AIRFLOW = {flow: name for name, flow in FAN_MODE_TRANSLATION.items()}

SUPPORTED_FAN_MODES = [
    FAN_AUTO,
    FAN_QUIET,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
]
