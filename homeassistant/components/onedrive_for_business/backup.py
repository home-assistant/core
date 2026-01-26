"""Support for OneDrive for Business backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
from json import dumps, loads
import logging
from time import time
from typing import Any, Concatenate

from aiohttp import ClientTimeout
from onedrive_personal_sdk.clients.large_file_upload import LargeFileUploadClient
from onedrive_personal_sdk.exceptions import HashMismatchError, OneDriveException
from onedrive_personal_sdk.models.upload import FileInfo

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import OneDriveConfigEntry
from .const import CONF_FOLDER_ID, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
MAX_CHUNK_SIZE = 60 * 1024 * 1024  # largest chunk possible, must be <= 60 MiB
TARGET_CHUNKS = 20
TIMEOUT = ClientTimeout(connect=10, total=43200)  # 12 hours
CACHE_TTL = 300


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[OneDriveConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    return [OneDriveBackupAgent(hass, entry) for entry in entries]


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


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors."""

    @wraps(func)
    async def wrapper(
        self: OneDriveBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except OneDriveException as err:
            _LOGGER.error(
                "Error during backup in %s: message %s",
                func.__name__,
                err,
            )
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError("Backup operation failed") from err
        except TimeoutError as err:
            _LOGGER.error(
                "Error during backup in %s: Timeout",
                func.__name__,
            )
            raise BackupAgentError("Backup operation timed out") from err

    return wrapper


@dataclass(kw_only=True)
class OneDriveBackup:
    """Define a OneDrive backup."""

    backup: AgentBackup
    backup_file_id: str
    metadata_file_id: str


class OneDriveBackupAgent(BackupAgent):
    """OneDrive backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
        """Initialize the OneDrive backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._client = entry.runtime_data.client
        self._token_function = entry.runtime_data.token_function
        self._folder_id = entry.data[CONF_FOLDER_ID]
        self.name = entry.title
        assert entry.unique_id
        self.unique_id = entry.unique_id
        self._backup_cache: dict[str, OneDriveBackup] = {}
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        backups = await self._list_cached_backups()
        if backup_id not in backups:
            raise BackupNotFound(f"Backup {backup_id} not found")

        stream = await self._client.download_drive_item(
            backups[backup_id].backup_file_id, timeout=TIMEOUT
        )
        return stream.iter_chunked(1024)

    @handle_backup_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        filename = suggested_filename(backup)
        file = FileInfo(
            filename,
            backup.size,
            self._folder_id,
            await open_stream(),
        )

        # determine chunk based on target chunks
        upload_chunk_size = backup.size / TARGET_CHUNKS
        # find the nearest multiple of 320KB
        upload_chunk_size = round(upload_chunk_size / (320 * 1024)) * (320 * 1024)
        # limit to max chunk size
        upload_chunk_size = min(upload_chunk_size, MAX_CHUNK_SIZE)
        # ensure minimum chunk size of 320KB
        upload_chunk_size = max(upload_chunk_size, 320 * 1024)

        try:
            backup_file = await LargeFileUploadClient.upload(
                self._token_function,
                file,
                upload_chunk_size=upload_chunk_size,
                session=async_get_clientsession(self._hass),
            )
        except HashMismatchError as err:
            raise BackupAgentError(
                "Hash validation failed, backup file might be corrupt"
            ) from err

        # store metadata in metadata file
        description = dumps(backup.as_dict())
        _LOGGER.debug("Creating metadata: %s", description)
        metadata_filename = filename.rsplit(".", 1)[0] + ".metadata.json"
        try:
            await self._client.upload_file(
                self._folder_id,
                metadata_filename,
                description,
            )
        except OneDriveException:
            await self._client.delete_drive_item(backup_file.id)
            raise

        self._cache_expiration = time()

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        backups = await self._list_cached_backups()
        if backup_id not in backups:
            raise BackupNotFound(f"Backup {backup_id} not found")

        backup = backups[backup_id]

        await self._client.delete_drive_item(backup.backup_file_id)
        await self._client.delete_drive_item(backup.metadata_file_id)
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return [
            backup.backup for backup in (await self._list_cached_backups()).values()
        ]

    @handle_backup_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Return a backup."""
        backups = await self._list_cached_backups()
        if backup_id not in backups:
            raise BackupNotFound(f"Backup {backup_id} not found")
        return backups[backup_id].backup

    async def _list_cached_backups(self) -> dict[str, OneDriveBackup]:
        """List backups with a cache."""
        if time() <= self._cache_expiration:
            return self._backup_cache

        items = await self._client.list_drive_items(self._folder_id)
        item_names = {item.name: item for item in items}

        # Filter metadata files
        metadata_files = [
            item for item in items if item.name.endswith(".metadata.json")
        ]

        async def download_backup_metadata(item_id: str) -> AgentBackup | None:
            try:
                metadata_stream = await self._client.download_drive_item(item_id)
            except OneDriveException as err:
                _LOGGER.warning("Error downloading metadata for %s: %s", item_id, err)
                return None
            metadata_json = loads(await metadata_stream.read())
            return AgentBackup.from_dict(metadata_json)

        backups: dict[str, OneDriveBackup] = {}
        for metadata_item in metadata_files:
            # Get the corresponding backup filename by removing ".metadata.json" and adding ".tar"
            backup_filename = metadata_item.name.replace(".metadata.json", ".tar")

            # Check if the corresponding backup file exists
            if backup_filename not in item_names:
                _LOGGER.warning(
                    "Backup file %s not found for metadata %s",
                    backup_filename,
                    metadata_item.name,
                )
                continue

            backup_item = item_names[backup_filename]

            # Download and parse metadata
            backup = await download_backup_metadata(metadata_item.id)
            if backup is None:
                continue

            backups[backup.backup_id] = OneDriveBackup(
                backup=backup,
                backup_file_id=backup_item.id,
                metadata_file_id=metadata_item.id,
            )

        self._cache_expiration = time() + CACHE_TTL
        self._backup_cache = backups
        return backups
