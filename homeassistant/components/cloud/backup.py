"""Backup platform for the cloud integration."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from aiohttp import ClientResponseError
from hass_nabucasa import Cloud
from hass_nabucasa.cloud_api import (
    async_files_delete_file,
    async_files_download_details,
    async_files_list,
    async_files_upload_details,
)

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    read_backup,
)
from homeassistant.core import HomeAssistant, callback

from .client import CloudClient
from .const import DATA_CLOUD, DOMAIN

_STORAGE_BACKUP = "backup"


def b64md5(path: Path) -> str:
    """Calculate the MD5 hash of a file."""
    with open(path, "rb") as f:
        file_hash = hashlib.md5()
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return base64.b64encode(file_hash.digest()).decode()


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the cloud backup agent."""
    return [CloudBackupAgent(hass=hass, cloud=hass.data[DATA_CLOUD])]


class CloudBackupAgent(BackupAgent):
    """Cloud backup agent."""

    name = DOMAIN

    def __init__(self, hass: HomeAssistant, cloud: Cloud[CloudClient]) -> None:
        """Initialize the cloud backup sync agent."""
        super().__init__()
        self._cloud = cloud
        self._hass = hass

    @callback
    def _get_backup_filename(self) -> str:
        """Return the backup filename."""
        return f"{self._cloud.client.prefs.instance_id}.tar"

    async def async_download_backup(
        self,
        backup_id: str,
        *,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :param path: The full file path to download the backup to.
        """
        if not self._cloud.is_logged_in:
            raise BackupAgentError("Not logged in to cloud")

        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        details = await async_files_download_details(
            self._cloud,
            storage_type=_STORAGE_BACKUP,
            filename=self._get_backup_filename(),
        )

        resp = await self._cloud.websession.get(
            details["url"],
            raise_for_status=True,
        )

        file = await self._hass.async_add_executor_job(path.open, "wb")
        async for chunk, _ in resp.content.iter_chunks():
            await self._hass.async_add_executor_job(file.write, chunk)

        metadata = await self._hass.async_add_executor_job(read_backup, path)
        if metadata.backup_id != backup_id:
            raise BackupAgentError("Backup not found")

    async def async_upload_backup(
        self,
        *,
        path: Path,
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param path: The full file path to the backup that should be uploaded.
        :param backup: Metadata about the backup that should be uploaded.
        """
        if not backup.protected:
            raise BackupAgentError("Cloud backups must be protected")

        if not self._cloud.is_logged_in:
            raise BackupAgentError("Not logged in to cloud")

        base64md5hash = await self._hass.async_add_executor_job(b64md5, path)

        details = await async_files_upload_details(
            self._cloud,
            storage_type=_STORAGE_BACKUP,
            filename=self._get_backup_filename(),
            metadata=backup.as_dict(),
            size=backup.size,
            base64md5hash=base64md5hash,
        )

        try:
            upload_status = await self._cloud.websession.put(
                details["url"],
                data=await self._hass.async_add_executor_job(path.open, "rb"),
                headers=details["headers"],
                raise_for_status=True,
            )

            upload_status.raise_for_status()
        except ClientResponseError as err:
            raise BackupAgentError("Failed to upload backup") from err

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        await async_files_delete_file(
            self._cloud,
            storage_type=_STORAGE_BACKUP,
            filename=self._get_backup_filename(),
        )

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups = await async_files_list(self._cloud, storage_type=_STORAGE_BACKUP)

        return [AgentBackup.from_dict(backup["Metadata"]) for backup in backups]

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
