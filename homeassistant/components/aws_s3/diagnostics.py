"""Diagnostics support for AWS S3."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.backup import (
    DATA_MANAGER as BACKUP_DATA_MANAGER,
    BackupManager,
)
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_PREFIX,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from .coordinator import S3ConfigEntry
from .helpers import async_list_backups_from_s3

TO_REDACT = (CONF_ACCESS_KEY_ID, CONF_SECRET_ACCESS_KEY)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: S3ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    backup_manager: BackupManager = hass.data[BACKUP_DATA_MANAGER]
    backups = await async_list_backups_from_s3(
        coordinator.client,
        bucket=entry.data[CONF_BUCKET],
        prefix=entry.data.get(CONF_PREFIX, ""),
    )

    data = {
        "coordinator_data": dataclasses.asdict(coordinator.data),
        "config": {
            **entry.data,
            **entry.options,
        },
        "backup_agents": [
            {"name": agent.name}
            for agent in backup_manager.backup_agents.values()
            if agent.domain == DOMAIN
        ],
        "backup": [backup.as_dict() for backup in backups],
    }

    return async_redact_data(data, TO_REDACT)
