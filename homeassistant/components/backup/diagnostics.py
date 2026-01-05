"""Diagnostics support for Home Assistant Backup integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import BackupConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BackupConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "backup_agents": [
            {"name": agent.name, "agent_id": agent.agent_id}
            for agent in coordinator.backup_manager.backup_agents.values()
        ],
        "backup_config": async_redact_data(
            coordinator.backup_manager.config.data.to_dict(), [CONF_PASSWORD]
        ),
    }
