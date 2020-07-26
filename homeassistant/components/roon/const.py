"""Constants for Roon Component."""
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "roon"

DATA_CONFIGS = "roon_configs"

DEFAULT_NAME = "Roon Labs Music Player"

ROON_APPINFO = {
    "extension_id": "home_assistant",
    "display_name": "Roon Integration for Home Assistant",
    "display_version": "1.0.0",
    "publisher": "home_assistant",
    "email": "home_assistant@users.noreply.github.com",
    "website": "https://www.home-assistant.io/",
}


class RoonException(HomeAssistantError):
    """Base class for Roon exceptions."""


class CannotConnect(RoonException):
    """Unable to connect to the server."""


class AuthenticationRequired(RoonException):
    """Unknown error occurred."""
