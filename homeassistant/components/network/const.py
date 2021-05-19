"""Constants for the network integration."""
from __future__ import annotations

DOMAIN = "network"
STORAGE_KEY = "core.network"
STORAGE_VERSION = 1

ATTR_ADAPTERS = "adapters"
ATTR_CONFIGURED_ADAPTERS = "configured_adapters"
DEFAULT_CONFIGURED_ADAPTERS: list[str] = []
