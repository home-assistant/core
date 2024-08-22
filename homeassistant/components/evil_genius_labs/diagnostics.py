"""Diagnostics support for Evil Genius Labs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import EvilGeniusUpdateCoordinator

TO_REDACT = {"wiFiSsidDefault", "wiFiSSID"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EvilGeniusUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "info": async_redact_data(coordinator.info, TO_REDACT),
        "all": coordinator.data,
    }
