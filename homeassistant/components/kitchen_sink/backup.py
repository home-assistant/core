"""Backup platform for the kitchen_sink integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.backup import (
    BackupAgent,
    BackupUploadMetadata,
    BaseBackup,
)
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    return [KitchenSinkBackupAgent("syncer")]


class KitchenSinkBackupAgent(BackupAgent):
    """Kitchen sink backup agent."""

    def __init__(self, name: str) -> None:
        """Initialize the kitchen sink backup sync agent."""
        super().__init__()
        self.name = name
        self._uploads = [
            BaseBackup(
                backup_id="abc123",
                date="1970-01-01T00:00:00Z",
                name="Kitchen sink syncer",
                protected=False,
                size=1234,
            )
        ]

    async def async_download_backup(
        self,
        backup_id: str,
        *,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file."""
        LOGGER.info("Downloading backup %s to %s", backup_id, path)

    async def async_upload_backup(
        self,
        *,
        path: Path,
        metadata: BackupUploadMetadata,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        LOGGER.info("Uploading backup %s %s", path.name, metadata)
        self._uploads.append(
            BaseBackup(
                backup_id=metadata.backup_id,
                date=metadata.date,
                name=metadata.name,
                protected=metadata.protected,
                size=metadata.size,
            )
        )

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        self._uploads = [
            upload for upload in self._uploads if upload.backup_id != backup_id
        ]
        LOGGER.info("Deleted backup %s", backup_id)

    async def async_list_backups(self, **kwargs: Any) -> list[BaseBackup]:
        """List synced backups."""
        return self._uploads

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> BaseBackup | None:
        """Return a backup."""
        for backup in self._uploads:
            if backup.backup_id == backup_id:
                return backup
        return None
