"""HALO Home integration constants."""
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "halohome"
CONF_LOCATIONS: Final = "locations"
PLATFORMS: Final = [
    Platform.LIGHT,
]
