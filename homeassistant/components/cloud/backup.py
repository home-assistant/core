"""Backup platform for the cloud integration."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Callable, Coroutine
import hashlib
from typing import Any, Self

from aiohttp import ClientError, StreamReader
from hass_nabucasa import Cloud, CloudError
from hass_nabucasa.cloud_api import (
    async_files_delete_file,
    async_files_download_details,
    async_files_list,
    async_files_upload_details,
)

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback

from .client import CloudClient
from .const import DATA_CLOUD, DOMAIN

_STORAGE_BACKUP = "backup"


async def _b64md5(stream: AsyncIterator[bytes]) -> str:
    """Calculate the MD5 hash of a file."""
    file_hash = hashlib.md5()
    async for chunk in stream:
        file_hash.update(chunk)
    return base64.b64encode(file_hash.digest()).decode()


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return the cloud backup agent."""
    cloud = hass.data[DATA_CLOUD]
    if not cloud.is_logged_in:
        return []

    return [CloudBackupAgent(hass=hass, cloud=cloud)]


class ChunkAsyncStreamIterator:
    """Async iterator for chunked streams.

    Based on aiohttp.streams.ChunkTupleAsyncStreamIterator, but yields
    bytes instead of tuple[bytes, bool].
    """

    __slots__ = ("_stream",)

    def __init__(self, stream: StreamReader) -> None:
        """Initialize."""
        self._stream = stream

    def __aiter__(self) -> Self:
        """Iterate."""
        return self

    async def __anext__(self) -> bytes:
        """Yield next chunk."""
        rv = await self._stream.readchunk()
        if rv == (b"", False):
            raise StopAsyncIteration
        return rv[0]


class CloudBackupAgent(BackupAgent):
    """Cloud backup agent."""

    domain = DOMAIN
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
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        try:
            details = await async_files_download_details(
                self._cloud,
                storage_type=_STORAGE_BACKUP,
                filename=self._get_backup_filename(),
            )
        except (ClientError, CloudError) as err:
            raise BackupAgentError("Failed to get download details") from err

        try:
            resp = await self._cloud.websession.get(details["url"])
            resp.raise_for_status()
        except ClientError as err:
            raise BackupAgentError("Failed to download backup") from err

        return ChunkAsyncStreamIterator(resp.content)

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param open_stream: A function returning an async iterator that yields bytes.
        :param backup: Metadata about the backup that should be uploaded.
        """
        if not backup.protected:
            raise BackupAgentError("Cloud backups must be protected")

        base64md5hash = await _b64md5(await open_stream())

        try:
            details = await async_files_upload_details(
                self._cloud,
                storage_type=_STORAGE_BACKUP,
                filename=self._get_backup_filename(),
                metadata=backup.as_dict(),
                size=backup.size,
                base64md5hash=base64md5hash,
            )
        except (ClientError, CloudError) as err:
            raise BackupAgentError("Failed to get upload details") from err

        try:
            upload_status = await self._cloud.websession.put(
                details["url"],
                data=await open_stream(),
                headers=details["headers"] | {"content-length": str(backup.size)},
            )
            upload_status.raise_for_status()
        except ClientError as err:
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

        try:
            await async_files_delete_file(
                self._cloud,
                storage_type=_STORAGE_BACKUP,
                filename=self._get_backup_filename(),
            )
        except (ClientError, CloudError) as err:
            raise BackupAgentError("Failed to delete backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        try:
            backups = await async_files_list(self._cloud, storage_type=_STORAGE_BACKUP)
        except (ClientError, CloudError) as err:
            raise BackupAgentError("Failed to list backups") from err

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
