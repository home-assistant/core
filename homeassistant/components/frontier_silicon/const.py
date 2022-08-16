"""Constants for the Frontier Silicon Media Player integration."""
from homeassistant.components.media_player.const import MEDIA_TYPE_CHANNEL

DOMAIN = "frontier_silicon"

DEFAULT_PIN = "1234"
DEFAULT_PORT = 80

MEDIA_TYPE_PRESET = "preset"

MEDIA_TYPE_LIBRARY = "library"

SUPPORTED_MEDIA_TYPES = [MEDIA_TYPE_CHANNEL, MEDIA_TYPE_PRESET]
