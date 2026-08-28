"""Constants for the Bitcoin integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "bitcoin"

DEFAULT_CURRENCY: Final = "USD"

INTEGRATION_TITLE: Final = "Bitcoin"

SCAN_INTERVAL: Final = timedelta(minutes=5)
