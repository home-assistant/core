"""Constants for the Canary integration."""

from typing import Final

DOMAIN: Final = "canary"

MANUFACTURER: Final = "Canary Connect, Inc"

# Configuration
CONF_FFMPEG_ARGUMENTS: Final = "ffmpeg_arguments"

# Defaults
DEFAULT_FFMPEG_ARGUMENTS: Final = "-pred 1"
DEFAULT_TIMEOUT: Final = 10
