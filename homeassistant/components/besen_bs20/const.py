"""Constants for the Besen BS20 integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "besen_bs20"
NAME: Final = "Besen BS20"

PLATFORMS: Final = [Platform.SWITCH]

CONF_SYNC_CLOCK: Final = "sync_clock"
DEFAULT_SYNC_CLOCK: Final = True
