"""Diagnostics support for IMAP."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import ImapDataUpdateCoordinator

REDACT_CONFIG = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return _async_get_diagnostics(hass, entry)


@callback
def _async_get_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    redacted_config = async_redact_data(entry.data, REDACT_CONFIG)
    coordinator: ImapDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "config": redacted_config,
        "event": coordinator.diagnostics_data,
    }
