"""Constants for the Just Nimbus integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN = "just_nimbus"

VOLUME_FLOW_RATE_LITERS_PER_MINUTE: Final = "L/m"

PLATFORMS = [
    Platform.SENSOR,
]
