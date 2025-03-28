"""Diagnostics support for Acaia."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .common import LcConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: LcConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    engine = entry.runtime_data

    # collect all data sources
    diagnostics: dict[str, Any] = {
        "config_entry": async_redact_data(entry, {}),
        "model": engine.systemInfo.Model,
        "device_state": engine.state.name,
        "mac": engine.systemInfo.MACAddress,
    }

    _LOGGER.debug("Diagnostics: %s", diagnostics)

    return diagnostics
