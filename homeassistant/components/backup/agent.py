"""Backup agents for the Backup integration."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from homeassistant.core import HomeAssistant

from .models import BackupUploadMetadata, BaseBackup


@dataclass(slots=True)
class UploadedBackup(BaseBackup):
    """Uploaded backup class."""

    id: str


class BackupAgent(abc.ABC):
    """Backup agent interface."""

    name: str

    @abc.abstractmethod
    async def async_download_backup(
        self,
        *,
        id: str,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file.

        :param id: The ID of the backup that was returned in async_list_backups.
        :param path: The full file path to download the backup to.
        """

    @abc.abstractmethod
    async def async_upload_backup(
        self,
        *,
        path: Path,
        metadata: BackupUploadMetadata,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param path: The full file path to the backup that should be uploaded.
        :param metadata: Metadata about the backup that should be uploaded.
        """

    @abc.abstractmethod
    async def async_list_backups(self, **kwargs: Any) -> list[UploadedBackup]:
        """List backups."""


class BackupAgentPlatformProtocol(Protocol):
    """Define the format of backup platforms which implement backup agents."""

    async def async_get_backup_agents(
        self,
        hass: HomeAssistant,
        **kwargs: Any,
    ) -> list[BackupAgent]:
        """Return a list of backup agents."""
