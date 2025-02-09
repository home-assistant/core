"""Backup platform for the cloud integration."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator, Callable, Coroutine, Mapping
import hashlib
import logging
import random
from typing import Any, Literal

from aiohttp import ClientError
from hass_nabucasa import Cloud, CloudError
from hass_nabucasa.api import CloudApiNonRetryableError
from hass_nabucasa.cloud_api import async_files_delete_file, async_files_list

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import ChunkAsyncStreamIterator
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .client import CloudClient
from .const import DATA_CLOUD, DOMAIN, EVENT_CLOUD_EVENT

_LOGGER = logging.getLogger(__name__)
_STORAGE_BACKUP: Literal["backup"] = "backup"
_RETRY_LIMIT = 5
_RETRY_SECONDS_MIN = 60
_RETRY_SECONDS_MAX = 600


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


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed."""

    @callback
    def unsub() -> None:
        """Unsubscribe from events."""
        unsub_signal()

    @callback
    def handle_event(data: Mapping[str, Any]) -> None:
        """Handle event."""
        if data["type"] not in ("login", "logout"):
            return
        listener()

    unsub_signal = async_dispatcher_connect(hass, EVENT_CLOUD_EVENT, handle_event)
    return unsub


class CloudBackupAgent(BackupAgent):
    """Cloud backup agent."""

    domain = name = unique_id = DOMAIN

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
            content = await self._cloud.files.download(
                storage_type=_STORAGE_BACKUP,
                filename=self._get_backup_filename(),
            )
        except CloudError as err:
            raise BackupAgentError(f"Failed to download backup: {err}") from err

        return ChunkAsyncStreamIterator(content)

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
        filename = self._get_backup_filename()
        metadata = backup.as_dict()
        size = backup.size

        tries = 1
        while tries <= _RETRY_LIMIT:
            try:
                await self._cloud.files.upload(
                    storage_type=_STORAGE_BACKUP,
                    open_stream=open_stream,
                    filename=filename,
                    base64md5hash=base64md5hash,
                    metadata=metadata,
                    size=size,
                )
                break
            except CloudApiNonRetryableError as err:
                if err.code == "NC-SH-FH-03":
                    raise BackupAgentError(
                        translation_domain=DOMAIN,
                        translation_key="backup_size_too_large",
                        translation_placeholders={
                            "size": str(round(size / (1024**3), 2))
                        },
                    ) from err
                raise BackupAgentError(f"Failed to upload backup {err}") from err
            except CloudError as err:
                if tries == _RETRY_LIMIT:
                    raise BackupAgentError(f"Failed to upload backup {err}") from err
                tries += 1
                retry_timer = random.randint(_RETRY_SECONDS_MIN, _RETRY_SECONDS_MAX)
                _LOGGER.info(
                    "Failed to upload backup, retrying (%s/%s) in %ss: %s",
                    tries,
                    _RETRY_LIMIT,
                    retry_timer,
                    err,
                )
                await asyncio.sleep(retry_timer)

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        if not await self.async_get_backup(backup_id):
            return

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
            _LOGGER.debug("Cloud backups: %s", backups)
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
