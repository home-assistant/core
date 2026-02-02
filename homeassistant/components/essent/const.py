"""Constants for the Essent integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Final

DOMAIN: Final = "essent"
UPDATE_INTERVAL: Final = timedelta(hours=12)
ATTRIBUTION: Final = "Data provided by Essent"


class EnergyType(StrEnum):
    """Supported energy types for Essent pricing."""

    ELECTRICITY = "electricity"
    GAS = "gas"


class PriceGroup(StrEnum):
    """Price group types as provided in tariff groups.

    VAT is not emitted as a price group; use tariff.total_amount_vat for VAT.
    """

    MARKET_PRICE = "MARKET_PRICE"
    PURCHASING_FEE = "PURCHASING_FEE"
    TAX = "TAX"
