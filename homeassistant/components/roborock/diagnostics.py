"""Support for the Airzone diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import RoborockConfigEntry

_LOGGER = logging.getLogger(__name__)

TO_REDACT_CONFIG = [
    "token",
    "sn",
    "rruid",
    CONF_UNIQUE_ID,
    "username",
    "uid",
    "h",
    "k",
    "s",
    "u",
    "avatarurl",
    "nickname",
    "tuyaUuid",
    "extra",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: RoborockConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = config_entry.runtime_data

    return {
        "config_entry": async_redact_data(config_entry.data, TO_REDACT_CONFIG),
        "coordinators": {
            f"**REDACTED-{i}**": coordinator.device.diagnostic_data()
            for i, coordinator in enumerate(coordinators.values())
        },
    }
