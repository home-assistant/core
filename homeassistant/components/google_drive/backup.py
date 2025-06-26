"""Backup platform for the Google Drive integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import logging
from typing import Any

from google_drive_api.exceptions import GoogleDriveApiError

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import ChunkAsyncStreamIterator
from homeassistant.util import slugify

from . import DATA_BACKUP_AGENT_LISTENERS, GoogleDriveConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return [GoogleDriveBackupAgent(entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed.

    :return: A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


class GoogleDriveBackupAgent(BackupAgent):
    """Google Drive backup agent."""

    domain = DOMAIN

    def __init__(self, config_entry: GoogleDriveConfigEntry) -> None:
        """Initialize the cloud backup sync agent."""
        super().__init__()
        assert config_entry.unique_id
        self.name = config_entry.title
        self.unique_id = slugify(config_entry.unique_id)
        self._client = config_entry.runtime_data

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
        try:
            await self._client.async_upload_backup(open_stream, backup)
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            raise BackupAgentError(f"Failed to upload backup: {err}") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        try:
            return await self._client.async_list_backups()
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            raise BackupAgentError(f"Failed to list backups: {err}") from err

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        backups = await self.async_list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup
        raise BackupNotFound(f"Backup {backup_id} not found")

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        _LOGGER.debug("Downloading backup_id: %s", backup_id)
        try:
            file_id = await self._client.async_get_backup_file_id(backup_id)
            if file_id:
                _LOGGER.debug("Downloading file_id: %s", file_id)
                stream = await self._client.async_download(file_id)
                return ChunkAsyncStreamIterator(stream)
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            raise BackupAgentError(f"Failed to download backup: {err}") from err
        raise BackupNotFound(f"Backup {backup_id} not found")

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        _LOGGER.debug("Deleting backup_id: %s", backup_id)
        try:
            file_id = await self._client.async_get_backup_file_id(backup_id)
            if file_id:
                _LOGGER.debug("Deleting file_id: %s", file_id)
                await self._client.async_delete(file_id)
                _LOGGER.debug("Deleted backup_id: %s", backup_id)
                return
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            raise BackupAgentError(f"Failed to delete backup: {err}") from err
        raise BackupNotFound(f"Backup {backup_id} not found")
