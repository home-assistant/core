"""Constants for the Besen BS20 integration."""

from typing import Final

from besen_bs20.const import (
    CHARGING_STATUS,
    CHARGING_STATUS_DESCRIPTIONS,
    CURRENT_STATE,
    ERRORS,
    FALLBACK_MAX_CHARGE_AMPS,
    LANGUAGES,
    MIN_CHARGE_AMPS,
    OUTPUT_STATE,
    PLUG_STATE,
    TEMPERATURE_UNITS,
)

DOMAIN: Final = "besen_bs20"
NAME: Final = "Besen BS20"
VERSION: Final = "0.2.0"

PLATFORMS: Final = [
    "sensor",
    "switch",
    "number",
    "select",
    "text",
]

CONF_SYNC_CLOCK: Final = "sync_clock"
DEFAULT_SYNC_CLOCK: Final = True

__all__ = [
    "CHARGING_STATUS",
    "CHARGING_STATUS_DESCRIPTIONS",
    "CONF_SYNC_CLOCK",
    "CURRENT_STATE",
    "DEFAULT_SYNC_CLOCK",
    "DOMAIN",
    "ERRORS",
    "FALLBACK_MAX_CHARGE_AMPS",
    "LANGUAGES",
    "MIN_CHARGE_AMPS",
    "NAME",
    "OUTPUT_STATE",
    "PLATFORMS",
    "PLUG_STATE",
    "TEMPERATURE_UNITS",
    "VERSION",
]
