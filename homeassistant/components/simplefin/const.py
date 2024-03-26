"""Constants for the SimpleFIN integration."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "simplefin"

LOGGER = logging.getLogger(__package__)

CONF_ACCESS_URL = "access_url"

ICON_CHECKING = "mdi:checkbook"
ICON_CREDIT_CARD = "mdi:credit-card"
ICON_SAVINGS = "mdi:piggy-bank-outline"
ICON_INVESTMENT = "mdi:chart-areaspline"
ICON_UNKNOWN = "mdi:cash"
