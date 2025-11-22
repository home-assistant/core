"""Constants for the Essent integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Final

DOMAIN: Final = "essent"
UPDATE_INTERVAL: Final = timedelta(hours=1)
ATTRIBUTION: Final = "Data provided by Essent"


class EnergyType(StrEnum):
    """Supported energy types for Essent pricing."""

    ELECTRICITY = "electricity"
    GAS = "gas"


# Price group types
PRICE_GROUP_MARKET: Final = "MARKET_PRICE"
PRICE_GROUP_PURCHASING_FEE: Final = "PURCHASING_FEE"
PRICE_GROUP_TAX: Final = "TAX"
