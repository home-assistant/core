"""Constants for the Emby integration."""

from homeassistant.const import Platform

DOMAIN = "emby"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8096
DEFAULT_SSL_PORT = 8920
DEFAULT_SSL = False

PLATFORMS = [Platform.MEDIA_PLAYER]


class CannotConnect(Exception):
    """Error to indicate a connection failure."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""
