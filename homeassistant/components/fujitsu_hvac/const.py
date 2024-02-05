"""Constants for the Fujitsu HVAC (based on Ayla IOT) integration."""
from ayla_iot_unofficial.fujitsu_hvac import FanSpeed, OpMode, SwingMode

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    HVACMode,
)

API = "api"
API_TIMEOUT = 10

DOMAIN = "fujitsu_hvac"
AYLA_APP_ID = "CJIOSP-id"
AYLA_APP_SECRET = "CJIOSP-Vb8MQL_lFiYQ7DKjN0eCFXznKZE"

CONF_EUROPE = "is_europe"

HA_TO_FUJI_FAN = {
    FAN_LOW: FanSpeed.LOW,
    FAN_MEDIUM: FanSpeed.MEDIUM,
    FAN_HIGH: FanSpeed.HIGH,
    FAN_AUTO: FanSpeed.AUTO,
}
HA_TO_FUJI_HVAC = {
    HVACMode.OFF: OpMode.OFF,
    HVACMode.HEAT: OpMode.HEAT,
    HVACMode.COOL: OpMode.COOL,
    HVACMode.AUTO: OpMode.AUTO,
    HVACMode.DRY: OpMode.DRY,
    HVACMode.FAN_ONLY: OpMode.FAN,
}
HA_TO_FUJI_SWING = {
    SWING_OFF: SwingMode.OFF,
    SWING_VERTICAL: SwingMode.SWING_VERTICAL,
    SWING_HORIZONTAL: SwingMode.SWING_HORIZONTAL,
    SWING_BOTH: SwingMode.SWING_BOTH,
}

FUJI_TO_HA_FAN = {
    FanSpeed.LOW: FAN_LOW,
    FanSpeed.MEDIUM: FAN_MEDIUM,
    FanSpeed.HIGH: FAN_HIGH,
    FanSpeed.AUTO: FAN_AUTO,
}
FUJI_TO_HA_HVAC = {
    OpMode.OFF: HVACMode.OFF,
    OpMode.HEAT: HVACMode.HEAT,
    OpMode.COOL: HVACMode.COOL,
    OpMode.AUTO: HVACMode.AUTO,
    OpMode.DRY: HVACMode.DRY,
    OpMode.FAN: HVACMode.FAN_ONLY,
}
FUJI_TO_HA_SWING = {
    SwingMode.OFF: SWING_OFF,
    SwingMode.SWING_VERTICAL: SWING_VERTICAL,
    SwingMode.SWING_HORIZONTAL: SWING_HORIZONTAL,
    SwingMode.SWING_BOTH: SWING_BOTH,
}
