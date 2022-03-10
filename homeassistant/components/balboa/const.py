"""Constants for the Balboa Spa Client integration."""
import logging

from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.const import Platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "balboa"

CLIMATE_SUPPORTED_FANSTATES = [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
CLIMATE_SUPPORTED_MODES = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]
CONF_SYNC_TIME = "sync_time"
DEFAULT_SYNC_TIME = False
PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE]

AUX = "Aux"
CIRC_PUMP = "Circ Pump"
CLIMATE = "Climate"
FILTER = "Filter"
LIGHT = "Light"
MISTER = "Mister"
PUMP = "Pump"
TEMP_RANGE = "Temp Range"

SIGNAL_UPDATE = "balboa_update_{}"
