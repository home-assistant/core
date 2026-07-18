"""Constants for the Silla Prism integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "silla_prism"

PLATFORMS: Final = [Platform.SENSOR]

CONF_BASE_TOPIC: Final = "base_topic"

DEFAULT_BASE_TOPIC: Final = "prism"

MANUFACTURER: Final = "Silla"
MODEL: Final = "Prism"

#: Charging port targeted by this integration. Single-cable Prisms only expose
#: port 1; DUO support (port 2) is intentionally left for a follow-up.
PORT: Final = 1
