"""Constants for the Snooz component."""

from homeassistant.const import Platform

DOMAIN = "snooz"
PLATFORMS: list[Platform] = [Platform.FAN]

SERVICE_TRANSITION_ON = "transition_on"
SERVICE_TRANSITION_OFF = "transition_off"

ATTR_VOLUME = "volume"
ATTR_DURATION = "duration"

DEFAULT_TRANSITION_DURATION = 20
