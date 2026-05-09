"""Constants for mijn.ista.nl integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mijn_ista"
MANUFACTURER: Final = "ista Nederland B.V."
DEVICE_NAME: Final = "mijn.ista.nl"

DEFAULT_UPDATE_INTERVAL: Final = 24  # hours
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Client-side translation for service names returned by the API in Dutch
SERVICE_NAME_TRANSLATIONS: Final[dict[str, str]] = {
    "Verwarming": "Heating",
    "Elektriciteit": "Electricity",
    "Koud water": "Cold water",
    "Warm water": "Hot water",
    "Gas": "Gas",
}
