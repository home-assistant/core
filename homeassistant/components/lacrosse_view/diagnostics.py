"""Diagnostics support for LaCrosse View."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LaCrosseUpdateCoordinator

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LaCrosseUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": coordinator.data,
    }
