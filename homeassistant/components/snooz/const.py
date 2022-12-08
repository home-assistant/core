"""Constants for the Snooz component."""

from homeassistant.const import Platform

DOMAIN = "snooz"
PLATFORMS: list[Platform] = [Platform.FAN]
SERVICE_FADE_ON = "fade_on"
SERVICE_FADE_OFF = "fade_off"
ATTR_VOLUME = "volume"
ATTR_DURATION = "duration"
DEFAULT_FADE_DURATION = 30
