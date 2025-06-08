"""Voluptuous schemas for eq3btsmart."""

from eq3btsmart.const import EQ3_MAX_TEMP, EQ3_MIN_TEMP
import voluptuous as vol

from homeassistant.const import CONF_MAC
from homeassistant.helpers import config_validation as cv

SCHEMA_TEMPERATURE = vol.Range(min=EQ3_MIN_TEMP, max=EQ3_MAX_TEMP)
SCHEMA_DEVICE = vol.Schema({vol.Required(CONF_MAC): cv.string})
SCHEMA_MAC = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
    }
)
