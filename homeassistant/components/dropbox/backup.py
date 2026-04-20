"""Backup platform for the Dropbox integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import json
import logging
from typing import Any, Concatenate

from python_dropbox_api import (
    DropboxAPIClient,
    DropboxAuthException,
    DropboxFileOrFolderNotFoundException,
    DropboxUnknownException,
)

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

from . import DropboxConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


async def _async_string_iterator(content: str) -> AsyncIterator[bytes]:
    """Yield a string as a single bytes chunk."""
    yield content.encode()


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
        self._api: DropboxAPIClient = entry.runtime_data

    async def _async_get_backups(self) -> list[tuple[AgentBackup, str]]:
        """Get backups and their corresponding file names."""
        files = await self._api.list_folder("")

        tar_files = {f.name for f in files if f.name.endswith(".tar")}
        metadata_files = [f for f in files if f.name.endswith(".metadata.json")]

        backups: list[tuple[AgentBackup, str]] = []
        for metadata_file in metadata_files:
            tar_name = metadata_file.name.removesuffix(".metadata.json") + ".tar"
            if tar_name not in tar_files:
                _LOGGER.warning(
                    "Found metadata file '%s' without matching backup file",
                    metadata_file.name,
                )
                continue

            metadata_stream = self._api.download_file(f"/{metadata_file.name}")
            raw = b"".join([chunk async for chunk in metadata_stream])
            try:
                data = json.loads(raw)
                backup = AgentBackup.from_dict(data)
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as err:
                _LOGGER.warning(
                    "Skipping invalid metadata file '%s': %s",
                    metadata_file.name,
                    err,
                )
                continue
            backups.append((backup, tar_name))

        return backups

    @handle_backup_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        backup_filename, metadata_filename = _suggested_filenames(backup)
        backup_path = f"/{backup_filename}"
        metadata_path = f"/{metadata_filename}"

        file_stream = await open_stream()
        await self._api.upload_file(backup_path, file_stream)

        metadata_stream = _async_string_iterator(json.dumps(backup.as_dict()))

        try:
            await self._api.upload_file(metadata_path, metadata_stream)
        except (
            DropboxAuthException,
            DropboxUnknownException,
        ):
            await self._api.delete_file(backup_path)
            raise

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return [backup for backup, _ in await self._async_get_backups()]

    @handle_backup_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        backups = await self._async_get_backups()
        for backup, filename in backups:
            if backup.backup_id == backup_id:
                return self._api.download_file(f"/{filename}")

        raise BackupNotFound(f"Backup {backup_id} not found")

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        backups = await self._async_get_backups()

        for backup, _ in backups:
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
        backups = await self._async_get_backups()
        for backup, tar_filename in backups:
            if backup.backup_id == backup_id:
                metadata_filename = tar_filename.removesuffix(".tar") + ".metadata.json"
                await self._api.delete_file(f"/{tar_filename}")
                await self._api.delete_file(f"/{metadata_filename}")
                return

        raise BackupNotFound(f"Backup {backup_id} not found")
