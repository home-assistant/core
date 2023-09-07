"""The constants for the Husqvarna Automower integration."""
from homeassistant.const import Platform

# Base component constants
NAME = "husqvarna_automower"
DOMAIN = "husqvarna_automower"
DOMAIN_DATA = f"{DOMAIN}_data"
HUSQVARNA_URL = "https://developer.husqvarnagroup.cloud/login"
OAUTH2_AUTHORIZE = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/authorize"
OAUTH2_TOKEN = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/token"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.LAWN_MOWER,
]


ERROR_STATES = ["ERROR", "FATAL_ERROR", "ERROR_AT_POWER_UP"]
ERROR_ACTIVITIES = ["STOPPED_IN_GARDEN", "UNKNOWN", "NOT_APPLICABLE"]
