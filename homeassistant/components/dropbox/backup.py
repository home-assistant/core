"""Backup platform for the Dropbox integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from python_dropbox_api import (
    DropboxAuthException,
    DropboxFileOrFolderNotFoundException,
    DropboxUnknownException,
)

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupNotFound
from homeassistant.components.backup.models import BackupAgentError
from homeassistant.core import HomeAssistant, callback

from . import DropboxConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return [DropboxBackupAgent(entry) for entry in entries]


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


class DropboxBackupAgent(BackupAgent):
    """Backup agent for the Dropbox integration."""

    domain = DOMAIN

    def __init__(self, entry: DropboxConfigEntry) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self.name = entry.title
        self.unique_id = entry.unique_id
        self._client = entry.runtime_data

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        try:
            await self._client.async_upload_backup(open_stream, backup)
        except (
            DropboxAuthException,
            DropboxFileOrFolderNotFoundException,
            DropboxUnknownException,
        ) as err:
            raise BackupAgentError("Failed to upload backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        try:
            return await self._client.async_list_backups()
        except (
            DropboxAuthException,
            DropboxFileOrFolderNotFoundException,
            DropboxUnknownException,
        ) as err:
            raise BackupAgentError("Failed to list backups") from err

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        try:
            return await self._client.async_download_backup(backup_id)
        except (
            DropboxAuthException,
            DropboxFileOrFolderNotFoundException,
            DropboxUnknownException,
        ) as err:
            raise BackupAgentError("Failed to download backup") from err

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        try:
            backups = await self.async_list_backups()
        except (
            DropboxAuthException,
            DropboxFileOrFolderNotFoundException,
            DropboxUnknownException,
        ) as err:
            raise BackupAgentError("Failed to get backup") from err

        for backup in backups:
            if backup.backup_id == backup_id:
                return backup

        raise BackupNotFound(f"Backup {backup_id} not found")

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        Raises BackupNotFound if the backup does not exist.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        try:
            await self._client.async_delete_backup(backup_id)
        except (
            DropboxAuthException,
            DropboxFileOrFolderNotFoundException,
            DropboxUnknownException,
        ) as err:
            raise BackupAgentError("Failed to delete backup") from err
