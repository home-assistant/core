"""Diagnostics support for the Casper Glow integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import CasperGlowConfigEntry

SERVICE_INFO_TO_REDACT = frozenset({"address", "name", "source", "device"})


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CasperGlowConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    service_info = bluetooth.async_last_service_info(
        hass, coordinator.device.address, connectable=True
    )

    return {
        "service_info": async_redact_data(
            service_info.as_dict() if service_info else None,
            SERVICE_INFO_TO_REDACT,
        ),
    }
