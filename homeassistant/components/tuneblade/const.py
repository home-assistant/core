"""Constants for TuneBlade integration."""

# Base component constants
NAME = "TuneBlade"
DOMAIN = "tuneblade"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "2025.06.8"
ISSUE_URL = "https://github.com/spycle/tuneblade/issues"

# Icons
ICON = "mdi:cast-audio-variant"

# Device classes
MEDIA_PLAYER_DEVICE_CLASS = "speaker"

# Platforms
SWITCH = "switch"
MEDIA_PLAYER = "media_player"
PLATFORMS = [SWITCH, MEDIA_PLAYER]

# Configuration and options
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_DEVICE_ID = "device_id"
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_NAME = DOMAIN

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
