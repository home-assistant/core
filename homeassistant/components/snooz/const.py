"""Constants for the Snooz component."""

from homeassistant.const import Platform

DOMAIN = "snooz"
PLATFORMS: list[Platform] = [Platform.FAN]

CONF_FIRMWARE_VERSION = "firmware_version"

DEFAULT_TRANSITION_DURATION = 20
