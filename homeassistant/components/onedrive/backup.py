"""Support for OneDrive backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import logging
from time import time
from typing import Any, Concatenate

from aiohttp import ClientTimeout
from onedrive_personal_sdk.clients.large_file_upload import LargeFileUploadClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    HashMismatchError,
    OneDriveException,
)
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
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads_object

from .const import CONF_DELETE_PERMANENTLY, DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .coordinator import OneDriveConfigEntry

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
        except AuthenticationError as err:
            self._entry.async_start_reauth(self._hass)
            raise BackupAgentError("Authentication error") from err
        except OneDriveException as err:
            _LOGGER.error(
                "Error during backup in %s:, message %s",
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


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


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
        self._folder_id = entry.runtime_data.backup_folder_id
        self.name = entry.title
        assert entry.unique_id
        self.unique_id = entry.unique_id
        self._cache_backup_metadata: dict[str, AgentBackup] = {}
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        backup = await self._find_backup_by_id(backup_id)
        backup_filename, _ = suggested_filenames(backup)

        stream = await self._client.download_drive_item(
            f"{self._folder_id}:/{backup_filename}:", timeout=TIMEOUT
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
        expires_at = self._entry.data["token"]["expires_at"]
        _LOGGER.debug(
            "Starting backup upload, token expiry: %s (in %s seconds)",
            expires_at,
            expires_at - time(),
        )
        backup_filename, metadata_filename = suggested_filenames(backup)
        file = FileInfo(
            backup_filename,
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
            await LargeFileUploadClient.upload(
                self._token_function,
                file,
                upload_chunk_size=upload_chunk_size,
                session=async_get_clientsession(self._hass),
                smart_chunk_size=True,
            )
        except HashMismatchError as err:
            raise BackupAgentError(
                "Hash validation failed, backup file might be corrupt"
            ) from err

        _LOGGER.debug("Uploaded backup to %s", backup_filename)

        # Store metadata in separate metadata file (just backup.as_dict(), no extra fields)
        metadata_content = json_dumps(backup.as_dict())
        try:
            await self._client.upload_file(
                self._folder_id,
                metadata_filename,
                metadata_content,
            )
        except OneDriveException:
            # Clean up the backup file if metadata upload fails
            _LOGGER.debug(
                "Uploading metadata failed, deleting backup file %s", backup_filename
            )
            await self._client.delete_drive_item(
                f"{self._folder_id}:/{backup_filename}:"
            )
            raise

        _LOGGER.debug("Uploaded metadata file %s", metadata_filename)
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        backup = await self._find_backup_by_id(backup_id)
        backup_filename, metadata_filename = suggested_filenames(backup)

        delete_permanently = self._entry.options.get(CONF_DELETE_PERMANENTLY, False)

        await self._client.delete_drive_item(
            f"{self._folder_id}:/{backup_filename}:", delete_permanently
        )
        await self._client.delete_drive_item(
            f"{self._folder_id}:/{metadata_filename}:", delete_permanently
        )

        _LOGGER.debug("Deleted backup %s", backup_filename)
        self._cache_expiration = time()

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return list((await self._list_cached_metadata_files()).values())

    @handle_backup_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _list_cached_metadata_files(self) -> dict[str, AgentBackup]:
        """List metadata files with a cache."""
        if time() <= self._cache_expiration:
            return self._cache_backup_metadata

        async def _download_metadata(item_id: str) -> AgentBackup | None:
            """Download metadata file."""
            try:
                metadata_stream = await self._client.download_drive_item(item_id)
            except OneDriveException as err:
                _LOGGER.warning("Error downloading metadata for %s: %s", item_id, err)
                return None

            return AgentBackup.from_dict(
                json_loads_object(await metadata_stream.read())
            )

        items = await self._client.list_drive_items(self._folder_id)

        # Build a set of backup filenames to check for orphaned metadata
        backup_filenames = {
            item.name for item in items if item.name and item.name.endswith(".tar")
        }

        metadata_files: dict[str, AgentBackup] = {}
        for item in items:
            if item.name and item.name.endswith(".metadata.json"):
                # Check if corresponding backup file exists
                backup_filename = f"{item.name[: -len('.metadata.json')]}.tar"
                if backup_filename not in backup_filenames:
                    _LOGGER.warning(
                        "Backup file %s not found for metadata %s",
                        backup_filename,
                        item.name,
                    )
                    continue
                if metadata := await _download_metadata(item.id):
                    metadata_files[metadata.backup_id] = metadata

        self._cache_backup_metadata = metadata_files
        self._cache_expiration = time() + CACHE_TTL
        return self._cache_backup_metadata

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its backup ID on remote."""
        metadata_files = await self._list_cached_metadata_files()
        if backup := metadata_files.get(backup_id):
            return backup

        raise BackupNotFound(f"Backup {backup_id} not found")
