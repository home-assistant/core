"""Constants for Roon Component."""
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

DOMAIN = "roon"

DATA_CONFIGS = "roon_configs"

CONF_CUSTOM_PLAY_ACTION = "custom_play_action"

ROON_APPINFO = {
    "extension_id": "home_assistant",
    "display_name": "Home Assistant",
    "display_version": "1.0.0",
    "publisher": "marcelveldt",
    "email": "marcelveldt@users.noreply.github.com",
    "website": "https://github.com/marcelveldt/roon-hass",
}

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_CUSTOM_PLAY_ACTION): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


class RoonException(HomeAssistantError):
    """Base class for Roon exceptions."""


class CannotConnect(RoonException):
    """Unable to connect to the server."""


class AuthenticationRequired(RoonException):
    """Unknown error occurred."""
