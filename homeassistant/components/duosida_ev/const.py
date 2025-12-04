"""Constants for the Duosida EV Charger integration."""

from typing import Final

DOMAIN: Final = "duosida_ev"
NAME: Final = "Duosida"

CONF_DEVICE_ID: Final = "device_id"

DEFAULT_PORT: Final = 9988
DEFAULT_SCAN_INTERVAL: Final = 30

STATUS_OPTIONS: Final[list[str]] = [
    "available",
    "preparing",
    "charging",
    "cooling",
    "suspended_ev",
    "finished",
    "holiday",
]
