"""Backup platform for the SFTP Storage integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from asyncssh.sftp import SFTPError

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.core import HomeAssistant, callback

from . import SFTPConfigEntry
from .client import BackupAgentClient
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN, LOGGER


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    entries: list[SFTPConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return [SFTPBackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed."""
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


class SFTPBackupAgent(BackupAgent):
    """SFTP Backup Storage agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: SFTPConfigEntry) -> None:
        """Initialize the SFTPBackupAgent backup sync agent."""
        super().__init__()
        self._entry: SFTPConfigEntry = entry
        self._hass: HomeAssistant = hass
        self.name: str = entry.title
        self.unique_id: str = entry.entry_id

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file from SFTP."""
        LOGGER.debug(
            "Establishing SFTP connection to remote host in order to download backup id: %s",
            backup_id,
        )
        try:
            # Will raise BackupAgentError if failure to authenticate or SFTP Permissions
            async with BackupAgentClient(self._entry, self._hass) as client:
                return await client.iter_file(backup_id)
        except FileNotFoundError as e:
            raise BackupNotFound(
                f"Unable to initiate download of backup id: {backup_id}. {e}"
            ) from e

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        LOGGER.debug("Received request to upload backup: %s", backup)
        iterator = await open_stream()

        LOGGER.debug(
            "Establishing SFTP connection to remote host in order to upload backup"
        )

        # Will raise BackupAgentError if failure to authenticate or SFTP Permissions
        async with BackupAgentClient(self._entry, self._hass) as client:
            LOGGER.debug("Uploading backup: %s", backup.backup_id)
            await client.async_upload_backup(iterator, backup)
        LOGGER.debug("Successfully uploaded backup id: %s", backup.backup_id)

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file from SFTP Storage."""
        LOGGER.debug("Received request to delete backup id: %s", backup_id)

        try:
            LOGGER.debug(
                "Establishing SFTP connection to remote host in order to delete backup"
            )
            # Will raise BackupAgentError if failure to authenticate or SFTP Permissions
            async with BackupAgentClient(self._entry, self._hass) as client:
                await client.async_delete_backup(backup_id)
        except FileNotFoundError as err:
            raise BackupNotFound(str(err)) from err
        except SFTPError as err:
            raise BackupAgentError(
                f"Failed to delete backup id: {backup_id}: {err}"
            ) from err

        LOGGER.debug("Successfully removed backup id: %s", backup_id)

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups stored on SFTP Storage."""

        # Will raise BackupAgentError if failure to authenticate or SFTP Permissions
        async with BackupAgentClient(self._entry, self._hass) as client:
            try:
                return await client.async_list_backups()
            except SFTPError as err:
                raise BackupAgentError(
                    f"Remote server error while attempting to list backups: {err}"
                ) from err

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        backups = await self.async_list_backups()

        for backup in backups:
            if backup.backup_id == backup_id:
                LOGGER.debug("Returning backup id: %s. %s", backup_id, backup)
                return backup

        raise BackupNotFound(f"Backup id: {backup_id} not found")
