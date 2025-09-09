"""Constants for the Fish Audio integration."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

# Integration domain
DOMAIN: Final = "fish_audio"

# Config / options keys
CONF_API_KEY: Final = "api_key"
CONF_VOICE_ID: Final = "voice_id"
CONF_LANGUAGE: Final = "language"
CONF_SORT_BY: Final = "sort_by"
CONF_SELF_ONLY: Final = "self_only"
CONF_BACKEND: Final = "backend"

# Credit balance thresholds (used by async_check_credit_balance in __init__.py)
# Tweak as needed for your product semantics.
CRITICAL_CREDIT_BALANCE: Final[Decimal] = Decimal("1.00")
WARNING_CREDIT_BALANCE: Final[Decimal] = Decimal("10.00")

# UI selector options
#
# These are fed directly into Home Assistant's SelectSelectorConfig(options=...)
# and should be either a list of strings or a list of {value,label} dicts.
# We use {value,label} so the UI shows nice labels while preserving stable values.
