"""Constants for the the iaqualink component."""
from datetime import timedelta

from homeassistant.components.climate.const import HVAC_MODE_HEAT, HVAC_MODE_OFF

DOMAIN = "iaqualink"
CLIMATE_SUPPORTED_MODES = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
UPDATE_INTERVAL = timedelta(seconds=30)
