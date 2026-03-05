"""Diagnostics platform for ISEO Argo BLE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import IseoConfigEntry

from .const import CONF_PRIV_SCALAR, CONF_UUID

TO_REDACT = {CONF_PRIV_SCALAR, CONF_UUID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IseoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {"config_entry_data": dict(entry.data)},
        TO_REDACT,
    )
