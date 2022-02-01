"""Constants for Unmanic integration."""

from homeassistant.const import Platform

# Base component constants
NAME = "Unmanic"
DOMAIN = "unmanic"
DEFAULT_NAME = "Unmanic"

# Platforms
PLATFORMS = [Platform.SENSOR]

# Defaults
DEFAULT_PORT = 8888
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_TIMEOUT = 8
