"""Support for WebDAV backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import logging
from time import time
from typing import Any, Concatenate

from aiohttp import ClientTimeout
from aiowebdav2.exceptions import UnauthorizedError, WebDavError
from propcache.api import cached_property

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads_object

from . import WebDavConfigEntry
from .const import CONF_BACKUP_PATH, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)

BACKUP_TIMEOUT = ClientTimeout(connect=10, total=43200)
CACHE_TTL = 300


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[WebDavConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return [WebDavBackupAgent(hass, entry) for entry in entries]


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


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[WebDavBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[WebDavBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors."""

    @wraps(func)
    async def wrapper(self: WebDavBackupAgent, *args: P.args, **kwargs: P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except UnauthorizedError as err:
            raise BackupAgentError("Authentication error") from err
        except WebDavError as err:
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(
                f"Backup operation failed: {err}",
            ) from err
        except TimeoutError as err:
            _LOGGER.error(
                "Error during backup in %s: Timeout",
                func.__name__,
            )
            raise BackupAgentError("Backup operation timed out") from err

    return wrapper


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


class WebDavBackupAgent(BackupAgent):
    """Backup agent interface."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: WebDavConfigEntry) -> None:
        """Initialize the WebDAV backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._client = entry.runtime_data
        self.name = entry.title
        self.unique_id = entry.entry_id
        self._cache_metadata_files: dict[str, AgentBackup] = {}
        self._cache_expiration = time()

    @cached_property
    def _backup_path(self) -> str:
        """Return the path to the backup."""
        return self._entry.data.get(CONF_BACKUP_PATH, "")

    @handle_backup_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        backup = await self._find_backup_by_id(backup_id)

        return await self._client.download_iter(
            f"{self._backup_path}/{suggested_filename(backup)}",
            timeout=BACKUP_TIMEOUT,
        )

    @handle_backup_errors
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
        (filename_tar, filename_meta) = suggested_filenames(backup)

        await self._client.upload_iter(
            await open_stream(),
            f"{self._backup_path}/{filename_tar}",
            timeout=BACKUP_TIMEOUT,
            content_length=backup.size,
        )

        _LOGGER.debug(
            "Uploaded backup to %s",
            f"{self._backup_path}/{filename_tar}",
        )

        await self._client.upload_iter(
            json_dumps(backup.as_dict()),
            f"{self._backup_path}/{filename_meta}",
        )

        _LOGGER.debug(
            "Uploaded metadata file for %s",
            f"{self._backup_path}/{filename_meta}",
        )

        # reset cache
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        backup = await self._find_backup_by_id(backup_id)

        (filename_tar, filename_meta) = suggested_filenames(backup)
        backup_path = f"{self._backup_path}/{filename_tar}"

        await self._client.clean(backup_path)
        await self._client.clean(f"{self._backup_path}/{filename_meta}")

        _LOGGER.debug(
            "Deleted backup at %s",
            backup_path,
        )

        # reset cache
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return list((await self._list_cached_metadata_files()).values())

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _list_cached_metadata_files(self) -> dict[str, AgentBackup]:
        """List metadata files with a cache."""
        if time() <= self._cache_expiration:
            return self._cache_metadata_files

        async def _download_metadata(path: str) -> AgentBackup:
            """Download metadata file."""
            iterator = await self._client.download_iter(path)
            metadata = await anext(iterator)
            return AgentBackup.from_dict(json_loads_object(metadata))

        async def _list_metadata_files() -> dict[str, AgentBackup]:
            """List metadata files."""
            files = await self._client.list_files(self._backup_path)
            return {
                metadata_content.backup_id: metadata_content
                for file_name in files
                if file_name.endswith(".metadata.json")
                if (metadata_content := await _download_metadata(file_name))
            }

        self._cache_metadata_files = await _list_metadata_files()
        self._cache_expiration = time() + CACHE_TTL
        return self._cache_metadata_files

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its backup ID on remote."""
        metadata_files = await self._list_cached_metadata_files()
        if metadata_file := metadata_files.get(backup_id):
            return metadata_file

        raise BackupNotFound(f"Backup {backup_id} not found")
