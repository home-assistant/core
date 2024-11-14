"""Backup platform for the kitchen_sink integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from homeassistant.components.backup import (
    BackupAgent,
    BackupUploadMetadata,
    UploadedBackup,
)
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


async def async_get_backup_sync_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    return [KitchenSinkBackupAgent("syncer")]


class KitchenSinkBackupAgent(BackupAgent):
    """Kitchen sink backup agent."""

    def __init__(self, name: str) -> None:
        """Initialize the kitchen sink backup sync agent."""
        super().__init__(name)
        self._uploads = [
            UploadedBackup(
                id="def456",
                name="Kitchen sink syncer",
                protected=False,
                slug="abc123",
                size=1234,
                date="1970-01-01T00:00:00Z",
            )
        ]

    async def async_download_backup(
        self,
        *,
        id: str,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file."""
        LOGGER.info("Downloading backup %s to %s", id, path)

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
            UploadedBackup(
                id=uuid4().hex,
                name=metadata.name,
                protected=metadata.protected,
                slug=metadata.slug,
                size=metadata.size,
                date=metadata.date,
            )
        )

    async def async_list_backups(self, **kwargs: Any) -> list[UploadedBackup]:
        """List synced backups."""
        return self._uploads
