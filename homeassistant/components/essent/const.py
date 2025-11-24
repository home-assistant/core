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


class PriceGroup(StrEnum):
    """Price group types."""

    MARKET_PRICE = "MARKET_PRICE"
    PURCHASING_FEE = "PURCHASING_FEE"
    TAX = "TAX"
