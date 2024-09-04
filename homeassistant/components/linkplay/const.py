"""LinkPlay constants."""

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

DOMAIN = "linkplay"
PLATFORMS = [Platform.MEDIA_PLAYER]
CONF_SESSION = "session"

SERVICE_PRESET = "preset"
ATTR_PRESET_NUMBER = "preset_number"

SERVICE_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRESET_NUMBER): cv.positive_int,
    }
)
