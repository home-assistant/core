"""Constants for the SPC integration."""

from typing import Final

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

DOMAIN: Final = "spc"

# Configuration
CONF_API_URL: Final = "api_url"
CONF_WS_URL: Final = "ws_url"

# Data
DATA_API: Final = "spc_api"
SIGNAL_UPDATE_ALARM: Final = "spc_update_alarm_{}"
SIGNAL_UPDATE_SENSOR: Final = "spc_update_sensor_{}"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL): cv.string,
        vol.Required(CONF_WS_URL): cv.string,
    }
)
