"""Diagnostics for the Minecraft Server integration."""

from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .coordinator import MinecraftServerConfigEntry

TO_REDACT: Iterable[Any] = {CONF_ADDRESS, "players_list"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MinecraftServerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        "config_entry": {
            "version": config_entry.version,
            "unique_id": config_entry.unique_id,
            "entry_id": config_entry.entry_id,
        },
        "config_entry_data": async_redact_data(config_entry.data, TO_REDACT),
        "config_entry_options": async_redact_data(config_entry.options, TO_REDACT),
        "server_data": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
