"""Backup platform for the Dropbox integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from python_dropbox_api import (
    DropboxAuthException,
    DropboxFileOrFolderNotFoundException,
    DropboxUnknownException,
)

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.core import HomeAssistant, callback

from . import DropboxConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[DropboxBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[DropboxBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors."""

    @wraps(func)
    async def wrapper(
        self: DropboxBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except DropboxFileOrFolderNotFoundException as err:
            raise BackupNotFound(
                f"Failed to {func.__name__.removeprefix('async_').replace('_', ' ')}"
            ) from err
        except DropboxAuthException as err:
            self._entry.async_start_reauth(self._hass)
            raise BackupAgentError("Authentication error") from err
        except DropboxUnknownException as err:
            _LOGGER.error(
                "Error during %s: %s",
                func.__name__,
                err,
            )
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(
                f"Failed to {func.__name__.removeprefix('async_').replace('_', ' ')}"
            ) from err

    return wrapper


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return [DropboxBackupAgent(hass, entry) for entry in entries]


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

    def __init__(self, hass: HomeAssistant, entry: DropboxConfigEntry) -> None:
        """Initialize the backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self.name = entry.title
        assert entry.unique_id
        self.unique_id = entry.unique_id
        self._client = entry.runtime_data

    @handle_backup_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        await self._client.async_upload_backup(open_stream, backup)

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return await self._client.async_list_backups()

    @handle_backup_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        return await self._client.async_download_backup(backup_id)

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        backups = await self._client.async_list_backups()

        for backup in backups:
            if backup.backup_id == backup_id:
                return backup

        raise BackupNotFound(f"Backup {backup_id} not found")

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        await self._client.async_delete_backup(backup_id)
