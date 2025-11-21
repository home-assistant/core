"""Constants for the Essent integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "essent"
API_ENDPOINT: Final = (
    "https://www.essent.nl/api/public/tariffmanagement/dynamic-prices/v1/"
)
UPDATE_INTERVAL: Final = timedelta(hours=1)
ATTRIBUTION: Final = "Data provided by Essent"

# Energy types
ENERGY_TYPE_ELECTRICITY: Final = "electricity"
ENERGY_TYPE_GAS: Final = "gas"

# Price group types
PRICE_GROUP_MARKET: Final = "MARKET_PRICE"
PRICE_GROUP_PURCHASING_FEE: Final = "PURCHASING_FEE"
PRICE_GROUP_TAX: Final = "TAX"
