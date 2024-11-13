"""Backup sync agents for the Backup integration."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from homeassistant.core import HomeAssistant

from .models import BackupSyncMetadata, BaseBackup


@dataclass(slots=True)
class SyncedBackup(BaseBackup):
    """Synced backup class."""

    id: str


class BackupSyncAgent(abc.ABC):
    """Define the format that backup sync agents can have."""

    def __init__(self, name: str) -> None:
        """Initialize the backup sync agent."""
        self.name = name

    @abc.abstractmethod
    async def async_download_backup(
        self,
        *,
        id: str,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file.

        The `id` parameter is the ID of the synced backup that was returned in async_list_backups.

        The `path` parameter is the full file path to download the synced backup to.
        """

    @abc.abstractmethod
    async def async_upload_backup(
        self,
        *,
        path: Path,
        metadata: BackupSyncMetadata,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        The `path` parameter is the full file path to the backup that should be synced.

        The `metadata` parameter contains metadata about the backup that should be synced.
        """

    @abc.abstractmethod
    async def async_list_backups(self, **kwargs: Any) -> list[SyncedBackup]:
        """List backups."""


class BackupPlatformAgentProtocol(Protocol):
    """Define the format that backup platforms can have."""

    async def async_get_backup_sync_agents(
        self,
        *,
        hass: HomeAssistant,
        **kwargs: Any,
    ) -> list[BackupSyncAgent]:
        """Register the backup sync agent."""
