"""Constants for the network integration."""
from __future__ import annotations

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

DOMAIN = "network"
STORAGE_KEY = "core.network"
STORAGE_VERSION = 1

ATTR_ADAPTERS = "adapters"
ATTR_CONFIGURED_ADAPTERS = "configured_adapters"
DEFAULT_CONFIGURED_ADAPTERS: list[str] = []

NETWORK_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(
            ATTR_CONFIGURED_ADAPTERS, default=DEFAULT_CONFIGURED_ADAPTERS
        ): vol.Schema(vol.All(cv.ensure_list, [cv.string])),
    }
)
