"""Constants for the Season integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "season"
PLATFORMS: Final = [Platform.SENSOR]

DEFAULT_NAME: Final = "Season"

TYPE_ASTRONOMICAL: Final = "astronomical"
TYPE_METEOROLOGICAL: Final = "meteorological"

VALID_TYPES: Final = [TYPE_ASTRONOMICAL, TYPE_METEOROLOGICAL]
