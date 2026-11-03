"""Constants for the Silla Prism integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "silla_prism"

PLATFORMS: Final = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

CONF_BASE_TOPIC: Final = "base_topic"

DEFAULT_BASE_TOPIC: Final = "prism"

MANUFACTURER: Final = "Silla"
MODEL: Final = "Prism"

#: Charging port targeted by this integration. Single-cable Prisms only expose
#: port 1; DUO support (port 2) is intentionally left for a follow-up.
PORT: Final = 1

#: Minimum/maximum charging current, in amps, as accepted by Prism.
MIN_CURRENT: Final = 6
MAX_CURRENT: Final = 32
