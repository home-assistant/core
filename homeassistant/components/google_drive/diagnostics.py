"""Diagnostics support for Google Drive."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.backup import (
    DATA_MANAGER as BACKUP_DATA_MANAGER,
    BackupManager,
)
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import GoogleDriveConfigEntry

TO_REDACT = (CONF_ACCESS_TOKEN, "refresh_token")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: GoogleDriveConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data
    backup_manager: BackupManager = hass.data[BACKUP_DATA_MANAGER]

    backups = await coordinator.client.async_list_backups()

    data = {
        "coordinator_data": dataclasses.asdict(coordinator.data),
        "config": {
            **entry.data,
            **entry.options,
        },
        "backup_folder_id": coordinator.backup_folder_id,
        "backup_agents": [
            {"name": agent.name}
            for agent in backup_manager.backup_agents.values()
            if agent.domain == DOMAIN
        ],
        "backup": [backup.as_dict() for backup in backups],
    }

    return async_redact_data(data, TO_REDACT)
