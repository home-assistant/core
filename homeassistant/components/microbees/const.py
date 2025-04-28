"""Constants for the microBees integration."""

from homeassistant.const import Platform

DOMAIN = "microbees"
OAUTH2_AUTHORIZE = "https://dev.microbees.com/oauth/authorize"
OAUTH2_TOKEN = "https://dev.microbees.com/oauth/token"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
