"""Diagnostics support for Modern Forms."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ModernFormsDataUpdateCoordinator

REDACT_CONFIG = {CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ModernFormsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if TYPE_CHECKING:
        assert coordinator is not None

    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "device": {
            "info": coordinator.modern_forms.info,
            "status": coordinator.modern_forms.status,
        },
    }
