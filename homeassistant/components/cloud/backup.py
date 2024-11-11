"""Backup platform for the cloud integration."""

from __future__ import annotations

from asyncio import StreamReader
import base64
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from hass_nabucasa import Cloud
from hass_nabucasa.cloud_api import (
    async_files_download_details,
    async_files_list,
    async_files_upload_details,
)
import securetar

from homeassistant.components.backup import (
    BackupSyncAgent,
    BackupSyncMetadata,
    SyncedBackup,
)
from homeassistant.core import HomeAssistant

from .client import CloudClient
from .const import DATA_CLOUD, DOMAIN

BUF_SIZE = 2**20 * 4  # 4MB


def b64md5(path: Path) -> str:
    """Calculate the MD5 hash of a file."""
    with open("your_filename.txt", "rb") as f:
        file_hash = hashlib.md5()
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return base64.b64encode(file_hash.digest()).decode()


async def async_get_backup_sync_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupSyncAgent]:
    """Register the backup sync agents."""
    hass.data[DOMAIN] = "cloud"
    return [CloudBackupSyncAgent(hass=hass, cloud=hass.data[DATA_CLOUD])]


class CloudBackupSyncAgent(BackupSyncAgent):
    """Cloud backup sync agent."""

    def __init__(self, hass: HomeAssistant, cloud: Cloud[CloudClient]) -> None:
        """Initialize the cloud backup sync agent."""
        super().__init__(name=DOMAIN)
        self.cloud = cloud
        self.hass = hass

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
        details = await async_files_download_details(
            self.cloud,
            storage_type="backup",
            id=id,
        )

        resp = await self.cloud.websession.get(
            details["url"],
            raise_for_status=True,
        )

        def _extract_inner_tar(content: StreamReader):
            """Extract the inner tar file."""
            with TemporaryDirectory() as tempdir:
                tempfile = Path(tempdir) / id
                for chunk in content.iter_any():
                    tempfile.write(chunk)
                with securetar.SecureTarFile(
                    tempfile,
                    "w",
                    gzip=True,
                    bufsize=BUF_SIZE,
                    key=self.cloud.client.prefs.backup_encryption_key,
                ) as outer_tar:
                    outer_tar.extract(id, path)

        await self.hass.async_add_executor_job(_extract_inner_tar, resp.content)

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
        if (
            not self.cloud.is_logged_in
            or self.cloud.client.prefs.backup_sync is not True
            or not self.cloud.client.prefs.backup_encryption_key
        ):
            return

        def _create_outer_tar():
            """Create the outer tar file."""
            tarfilepath = Path()
            with securetar.SecureTarFile(
                tarfilepath,
                "w",
                gzip=True,
                bufsize=BUF_SIZE,
                key=self.cloud.client.prefs.backup_encryption_key,
            ) as outer_tar:
                outer_tar.add(path, arcname=path.name)

            return tarfilepath, b64md5(tarfilepath), tarfilepath.stat().st_size

        tarfilepath, base64md5hash, size = await self.hass.async_add_executor_job(
            _create_outer_tar
        )

        details = await async_files_upload_details(
            self.cloud,
            storage_type="backup",
            name=f"{self.cloud.client.prefs.instance_id}.tar",
            metadata={
                "slug": metadata["slug"],
                "homeassistant_version": metadata["homeassistant"],
                "name": metadata["name"],
                "date": metadata["date"],
                "protected": metadata["protected"],
                "content": {},
            },
            size=size,
            base64md5hash=base64md5hash,
        )

        await self.cloud.websession.put(
            details["url"],
            data={"file": tarfilepath.open("rb")},
            headers=details["headers"],
        )

        await self.hass.async_add_executor_job(tarfilepath.unlink)

    async def async_list_backups(self, **kwargs: Any) -> list[SyncedBackup]:
        """List backups."""
        backups = await async_files_list(self.cloud)
        return [
            SyncedBackup(
                id=backup.Key,
                date=backup.LastModified,
                slug=backup.Metadata["slug"],
                name=backup.Metadata.get("name"),
            )
            for backup in backups
        ]
