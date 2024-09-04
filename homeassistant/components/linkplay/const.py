"""LinkPlay constants."""

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.helpers import config_validation as cv

DOMAIN = "linkplay"
PLATFORMS = [Platform.MEDIA_PLAYER]
CONF_SESSION = "session"

SERVICE_PRESET = "preset"
ATTR_PRESET = "preset"

SERVICE_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required(ATTR_PRESET): cv.positive_int,
    }
)
