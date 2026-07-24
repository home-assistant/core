"""Constants for the Noonlight integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "noonlight"

PLATFORMS: Final = [Platform.BINARY_SENSOR]

# How often (seconds) to probe Noonlight for reachability + a valid token.
POLL_INTERVAL: Final = 300
# Bogus alarm id used for the side-effect-free probe (GET status → 404 means
# reachable + authorized; 401 means the token is bad). Never creates an alarm.
PROBE_ALARM_ID: Final = "reachability-probe"
