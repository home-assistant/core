"""Diagnostics platform for Uptime Kuma."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import UptimeKumaConfigEntry

TO_REDACT = {"monitor_url", "monitor_hostname"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UptimeKumaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return async_redact_data(
        {k: asdict(v) for k, v in entry.runtime_data.data.items()}, TO_REDACT
    )
