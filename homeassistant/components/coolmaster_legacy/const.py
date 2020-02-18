"""Constants for the coolmaster_legacy integration."""

from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
)

CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
DEFAULT_BAUDRATE = 9600

AVAILABLE_MODES = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_FAN_ONLY,
]

DOMAIN = "coolmaster_legacy"
