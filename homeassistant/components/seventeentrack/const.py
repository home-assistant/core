"""Constants for the seventeentrack integration."""

from typing import Final

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN: Final = "seventeentrack"
SERVICE_ADD_TRACKING: Final = "add_tracking"

CONF_TRACKING_NUMBER: Final = "tracking_number"
CONF_FRIENDLY_NAME: Final = "friendly_name"

ADD_TRACKING_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_TRACKING_NUMBER): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    }
)
