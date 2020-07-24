"""Constants for Roon Component."""
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

DOMAIN = "roon"

DATA_CONFIGS = "roon_configs"


ROON_APPINFO = {
    "extension_id": "home_assistant",
    "display_name": "Roon Integration for Home Assistant",
    "display_version": "1.0.0",
    "publisher": "home_assistant",
    "email": "home_assistant@users.noreply.github.com",
    "website": "https://www.home-assistant.io/",
}

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(CONF_HOST): cv.string, vol.Optional(CONF_API_KEY): cv.string},
    extra=vol.ALLOW_EXTRA,
)


class RoonException(HomeAssistantError):
    """Base class for Roon exceptions."""


class CannotConnect(RoonException):
    """Unable to connect to the server."""


class AuthenticationRequired(RoonException):
    """Unknown error occurred."""
