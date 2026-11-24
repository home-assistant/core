"""Probatio schemas for eq3btsmart."""

from eq3btsmart.const import EQ3_MAX_TEMP, EQ3_MIN_TEMP
import probatio

from homeassistant.const import CONF_MAC
from homeassistant.helpers import config_validation as cv

SCHEMA_TEMPERATURE = probatio.Range(min=EQ3_MIN_TEMP, max=EQ3_MAX_TEMP)
SCHEMA_DEVICE = probatio.Schema({probatio.Required(CONF_MAC): cv.string})
SCHEMA_MAC = probatio.Schema(
    {
        probatio.Required(CONF_MAC): str,
    }
)
