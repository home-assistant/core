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
    """Define the format that backup agents can have."""

    def __init__(self, name: str) -> None:
        """Initialize the backup agent."""
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

        The `id` parameter is the ID of the backup that was returned in async_list_backups.

        The `path` parameter is the full file path to download the backup to.
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

        The `path` parameter is the full file path to the backup that should be uploaded.

        The `metadata` parameter contains metadata about the backup that should be uploaded.
        """

    @abc.abstractmethod
    async def async_list_backups(self, **kwargs: Any) -> list[UploadedBackup]:
        """List backups."""


class BackupAgentPlatformProtocol(Protocol):
    """Define the format that backup platforms can have."""

    async def async_get_backup_agents(
        self,
        *,
        hass: HomeAssistant,
        **kwargs: Any,
    ) -> list[BackupAgent]:
        """Register the backup agent."""
