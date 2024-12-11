"""Backup platform for the kitchen_sink integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
import logging
from typing import Any

from homeassistant.components.backup import AddonInfo, AgentBackup, BackupAgent, Folder
from homeassistant.core import HomeAssistant

from . import DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    return [KitchenSinkBackupAgent("syncer")]


class KitchenSinkBackupAgent(BackupAgent):
    """Kitchen sink backup agent."""

    domain = DOMAIN

    def __init__(self, name: str) -> None:
        """Initialize the kitchen sink backup sync agent."""
        super().__init__()
        self.name = name
        self._uploads = [
            AgentBackup(
                addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
                backup_id="abc123",
                database_included=False,
                date="1970-01-01T00:00:00Z",
                folders=[Folder.MEDIA, Folder.SHARE],
                homeassistant_included=True,
                homeassistant_version="2024.12.0",
                name="Kitchen sink syncer",
                protected=False,
                size=1234,
            )
        ]

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        LOGGER.info("Downloading backup %s", backup_id)
        reader = asyncio.StreamReader()
        reader.feed_data(b"backup data")
        reader.feed_eof()
        return reader

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        LOGGER.info("Uploading backup %s %s", backup.backup_id, backup)
        self._uploads.append(backup)

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

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List synced backups."""
        return self._uploads

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        for backup in self._uploads:
            if backup.backup_id == backup_id:
                return backup
        return None
