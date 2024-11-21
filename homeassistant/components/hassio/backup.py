"""Backup functionality for supervised installations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aiohasupervisor import backups as supervisor_backups

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupProgress,
    BackupReaderWriter,
    LocalBackupAgent,
    NewBackup,
)
from homeassistant.core import HomeAssistant

from .handler import get_supervisor_client


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the hassio backup agents."""
    return [SupervisorLocalBackupAgent(hass)]


class SupervisorLocalBackupAgent(LocalBackupAgent):
    """Local backup agent for supervised installations."""

    name = "local"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self._backup_dir = Path("/backups")
        self._client = get_supervisor_client(hass)

    async def async_download_backup(
        self,
        backup_id: str,
        *,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file."""
        raise NotImplementedError("Not yet supported by supervisor")

    async def async_upload_backup(
        self,
        *,
        path: Path,
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        await self._client.backups.reload()

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return [
            AgentBackup(
                addons=[],
                backup_id=backup.slug,
                database_included=True,
                date=backup.date.isoformat(),
                folders=backup.content.folders,
                homeassistant_included=backup.content.homeassistant,
                homeassistant_version="2024.12.0",
                name=backup.name,
                protected=backup.protected,
                size=int(backup.size * 2**20),
            )
            for backup in await self._client.backups.list()
        ]

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        backups = await self.async_list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup
        return None

    def get_backup_path(self, backup_id: str) -> Path:
        """Return the local path to a backup."""
        return self._backup_dir / f"{backup_id}.tar"

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Remove a backup."""
        raise NotImplementedError("Not yet supported by supervisor")


class SupervisorBackupReaderWriter(BackupReaderWriter):
    """Class for reading and writing backups in supervised installations."""

    temp_backup_dir = Path("/cloud_backups")

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the backup reader/writer."""
        self._hass = hass
        self._client = get_supervisor_client(hass)

    async def async_create_backup(
        self,
        *,
        addons_included: list[str] | None,
        agent_ids: list[str],
        database_included: bool,
        backup_name: str,
        folders_included: list[str] | None,
        on_progress: Callable[[BackupProgress], None] | None,
        password: str | None,
    ) -> tuple[NewBackup, asyncio.Task[tuple[AgentBackup, Path]]]:
        """Create a backup."""
        addons_included_set = set(addons_included) if addons_included else None
        folders_included_set = set(folders_included) if folders_included else None

        backup = await self._client.backups.partial_backup(
            supervisor_backups.PartialBackupOptions(
                addons=addons_included_set,
                folders=folders_included_set,  # type: ignore[arg-type]
                homeassistant=True,
                name=backup_name,
                password=password,
                compressed=True,
                location=None,
                homeassistant_exclude_database=not database_included,
                background=True,
            )
        )
        backup_task = self._hass.async_create_task(
            self._async_wait_for_backup(backup),
            name="backup_manager_create_backup",
            eager_start=False,  # To ensure the task is not started before we return
        )

        return (NewBackup(backup_job_id=backup.job_id), backup_task)

    async def _async_wait_for_backup(
        self, backup: supervisor_backups.NewBackup
    ) -> tuple[AgentBackup, Path]:
        """Wait for a backup to complete."""
        raise NotImplementedError

    async def async_restore_backup(
        self,
        backup_id: str,
        *,
        agent_id: str,
        password: str | None,
    ) -> None:
        """Restore a backup."""
        await self._client.backups.partial_restore(
            backup_id,
            supervisor_backups.PartialRestoreOptions(
                addons=None,
                folders=None,
                homeassistant=True,
                password=password,
                background=True,
            ),
        )
