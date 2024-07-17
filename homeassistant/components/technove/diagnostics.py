"""Diagnostics support for TechnoVE."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TechnoVEConfigEntry

TO_REDACT = {"unique_id", "mac_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TechnoVEConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(asdict(entry.runtime_data.data.info), TO_REDACT)
