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
