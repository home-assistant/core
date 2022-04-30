"""Constants for the network integration."""
from __future__ import annotations

from typing import Final

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN: Final = "network"
STORAGE_KEY: Final = "core.network"
STORAGE_VERSION: Final = 1

DATA_NETWORK: Final = "network"

ATTR_ADAPTERS: Final = "adapters"
ATTR_CONFIGURED_ADAPTERS: Final = "configured_adapters"
DEFAULT_CONFIGURED_ADAPTERS: list[str] = []

LOOPBACK_TARGET_IP: Final = "127.0.0.1"
MDNS_TARGET_IP: Final = "224.0.0.251"
PUBLIC_TARGET_IP: Final = "8.8.8.8"
IPV4_BROADCAST_ADDR: Final = "255.255.255.255"

NETWORK_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(
            ATTR_CONFIGURED_ADAPTERS, default=DEFAULT_CONFIGURED_ADAPTERS
        ): vol.Schema(vol.All(cv.ensure_list, [cv.string])),
    }
)
