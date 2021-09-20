"""Constants for the network integration."""
from __future__ import annotations

from typing import Final

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN: Final = "network"
STORAGE_KEY: Final = "core.network"
STORAGE_VERSION: Final = 1

ATTR_ADAPTERS: Final = "adapters"
ATTR_CONFIGURED_ADAPTERS: Final = "configured_adapters"
DEFAULT_CONFIGURED_ADAPTERS: list[str] = []

MDNS_TARGET_IP: Final = "224.0.0.251"


NETWORK_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(
            ATTR_CONFIGURED_ADAPTERS, default=DEFAULT_CONFIGURED_ADAPTERS
        ): vol.Schema(vol.All(cv.ensure_list, [cv.string])),
    }
)
