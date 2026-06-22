"""Constants for the Midea ccm15 AC Controller integration."""

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVACMode,
)

DOMAIN = "ccm15"
DEFAULT_TIMEOUT = 10
DEFAULT_INTERVAL = 30

CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
# CCM15 manual specifies 17-30 °C / 62-86 °F as the supported setpoint range.
DEFAULT_MIN_TEMP_C = 17
DEFAULT_MAX_TEMP_C = 30
DEFAULT_MIN_TEMP_F = 62
DEFAULT_MAX_TEMP_F = 86
DEFAULT_MIN_TEMP = DEFAULT_MIN_TEMP_C
DEFAULT_MAX_TEMP = DEFAULT_MAX_TEMP_C

CONST_STATE_CMD_MAP = {
    HVACMode.COOL: 0,
    HVACMode.HEAT: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.OFF: 4,
    HVACMode.AUTO: 5,
}
CONST_CMD_STATE_MAP = {v: k for k, v in CONST_STATE_CMD_MAP.items()}
CONST_FAN_CMD_MAP = {FAN_AUTO: 0, FAN_LOW: 2, FAN_MEDIUM: 3, FAN_HIGH: 4, FAN_OFF: 5}
CONST_CMD_FAN_MAP = {v: k for k, v in CONST_FAN_CMD_MAP.items()}
