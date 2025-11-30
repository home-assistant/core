"""Backup platform for the Backblaze B2 integration."""

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import json
import logging
import mimetypes
from time import time
from typing import Any

from b2sdk.v2 import FileVersion
from b2sdk.v2.exception import B2Error

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.async_iterator import AsyncIteratorReader

from . import BackblazeConfigEntry
from .const import (
    CONF_PREFIX,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    METADATA_FILE_SUFFIX,
    METADATA_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Cache TTL for backup list (in seconds)
CACHE_TTL = 300


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata files."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


def _parse_metadata(raw_content: str) -> dict[str, Any]:
    """Parse metadata content from JSON."""
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON format: {err}") from err
    else:
        if not isinstance(data, dict):
            raise TypeError("JSON content is not a dictionary")
        return data


def _find_backup_file_for_metadata(
    metadata_filename: str, all_files: dict[str, FileVersion], prefix: str
) -> FileVersion | None:
    """Find corresponding backup file for metadata file."""
    base_name = metadata_filename[len(prefix) :].removesuffix(METADATA_FILE_SUFFIX)
    return next(
        (
            file
            for name, file in all_files.items()
            if name.startswith(prefix + base_name)
            and name.endswith(".tar")
            and name != metadata_filename
        ),
        None,
    )


def _create_backup_from_metadata(
    metadata_content: dict[str, Any], backup_file: FileVersion
) -> AgentBackup:
    """Construct an AgentBackup from parsed metadata content and the associated backup file."""
    metadata = metadata_content["backup_metadata"]
    metadata["size"] = backup_file.size
    return AgentBackup.from_dict(metadata)


def handle_b2_errors[T](
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Handle B2Errors by converting them to BackupAgentError."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        """Catch B2Error and raise BackupAgentError."""
        try:
            return await func(*args, **kwargs)
        except B2Error as err:
            error_msg = f"Failed during {func.__name__}"
            raise BackupAgentError(error_msg) from err

    return wrapper


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents for all configured Backblaze B2 entries."""
    entries: list[BackblazeConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    return [BackblazeBackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when backup agents are added or removed.

    :return: A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            hass.data.pop(DATA_BACKUP_AGENT_LISTENERS, None)

    return remove_listener


class BackblazeBackupAgent(BackupAgent):
    """Backup agent for Backblaze B2 cloud storage."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: BackblazeConfigEntry) -> None:
        """Initialize the Backblaze B2 agent."""
        super().__init__()
        self._hass = hass
        self._bucket = entry.runtime_data
        self._prefix = entry.data[CONF_PREFIX]

        self.name = entry.title
        self.unique_id = entry.entry_id

        self._all_files_cache: dict[str, FileVersion] = {}
        self._all_files_cache_expiration: float = 0.0
        self._backup_list_cache: dict[str, AgentBackup] = {}
        self._backup_list_cache_expiration: float = 0.0

        self._all_files_cache_lock = asyncio.Lock()
        self._backup_list_cache_lock = asyncio.Lock()

    def _is_cache_valid(self, expiration_time: float) -> bool:
        """Check if cache is still valid based on expiration time."""
        return time() <= expiration_time

    async def _cleanup_failed_upload(self, filename: str) -> None:
        """Clean up a partially uploaded file after upload failure."""
        _LOGGER.warning(
            "Attempting to delete partially uploaded main backup file %s "
            "due to metadata upload failure",
            filename,
        )
        try:
            uploaded_main_file_info = await self._hass.async_add_executor_job(
                self._bucket.get_file_info_by_name, filename
            )
            await self._hass.async_add_executor_job(uploaded_main_file_info.delete)
        except B2Error:
            _LOGGER.debug(
                "Failed to clean up partially uploaded main backup file %s. "
                "Manual intervention may be required to delete it from Backblaze B2",
                filename,
                exc_info=True,
            )
        else:
            _LOGGER.debug(
                "Successfully deleted partially uploaded main backup file %s", filename
            )

    async def _get_file_for_download(self, backup_id: str) -> FileVersion:
        """Get backup file for download, raising if not found."""
        file, _ = await self._find_file_and_metadata_version_by_id(backup_id)
        if not file:
            raise BackupNotFound(f"Backup {backup_id} not found")
        return file

    @handle_b2_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup from Backblaze B2."""
        file = await self._get_file_for_download(backup_id)
        _LOGGER.debug("Downloading %s", file.file_name)

        downloaded_file = await self._hass.async_add_executor_job(file.download)
        response = downloaded_file.response

        async def stream_response() -> AsyncIterator[bytes]:
            """Stream the response into an AsyncIterator."""
            try:
                iterator = response.iter_content(chunk_size=1024 * 1024)
                while True:
                    chunk = await self._hass.async_add_executor_job(
                        next, iterator, None
                    )
                    if chunk is None:
                        break
                    yield chunk
            finally:
                _LOGGER.debug("Finished streaming download for %s", file.file_name)

        return stream_response()

    @handle_b2_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup to Backblaze B2.

        This involves uploading the main backup archive and a separate metadata JSON file.
        """
        tar_filename, metadata_filename = suggested_filenames(backup)
        prefixed_tar_filename = self._prefix + tar_filename
        prefixed_metadata_filename = self._prefix + metadata_filename

        metadata_content_bytes = json.dumps(
            {
                "metadata_version": METADATA_VERSION,
                "backup_id": backup.backup_id,
                "backup_metadata": backup.as_dict(),
            }
        ).encode("utf-8")

        _LOGGER.debug(
            "Uploading backup: %s, and metadata: %s",
            prefixed_tar_filename,
            prefixed_metadata_filename,
        )

        upload_successful = False
        try:
            await self._upload_backup_file(prefixed_tar_filename, open_stream, {})
            _LOGGER.debug(
                "Main backup file upload finished for %s", prefixed_tar_filename
            )

            _LOGGER.debug("Uploading metadata file: %s", prefixed_metadata_filename)
            await self._upload_metadata_file(
                metadata_content_bytes, prefixed_metadata_filename
            )
            _LOGGER.debug(
                "Metadata file upload finished for %s", prefixed_metadata_filename
            )
            upload_successful = True
        finally:
            if upload_successful:
                _LOGGER.debug("Backup upload complete: %s", prefixed_tar_filename)
                self._invalidate_caches(
                    backup.backup_id, prefixed_tar_filename, prefixed_metadata_filename
                )
            else:
                await self._cleanup_failed_upload(prefixed_tar_filename)

    def _upload_metadata_file_sync(
        self, metadata_content: bytes, filename: str
    ) -> None:
        """Synchronously upload metadata file to B2."""
        self._bucket.upload_bytes(
            metadata_content,
            filename,
            content_type="application/json",
            file_info={"metadata_only": "true"},
        )

    async def _upload_metadata_file(
        self, metadata_content: bytes, filename: str
    ) -> None:
        """Upload metadata file to B2."""
        await self._hass.async_add_executor_job(
            self._upload_metadata_file_sync,
            metadata_content,
            filename,
        )

    def _upload_unbound_stream_sync(
        self,
        reader: AsyncIteratorReader,
        filename: str,
        content_type: str,
        file_info: dict[str, Any],
    ) -> FileVersion:
        """Synchronously upload unbound stream to B2."""
        return self._bucket.upload_unbound_stream(
            reader,
            filename,
            content_type=content_type,
            file_info=file_info,
        )

    def _download_and_parse_metadata_sync(
        self, metadata_file_version: FileVersion
    ) -> dict[str, Any]:
        """Synchronously download and parse metadata file."""
        return _parse_metadata(
            metadata_file_version.download().response.content.decode("utf-8")
        )

    async def _upload_backup_file(
        self,
        filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        file_info: dict[str, Any],
    ) -> None:
        """Upload backup file to B2 using streaming."""
        _LOGGER.debug("Starting streaming upload for %s", filename)

        stream = await open_stream()
        reader = AsyncIteratorReader(self._hass.loop, stream)

        _LOGGER.debug("Uploading backup file %s with streaming", filename)
        try:
            content_type, _ = mimetypes.guess_type(filename)
            file_version = await self._hass.async_add_executor_job(
                self._upload_unbound_stream_sync,
                reader,
                filename,
                content_type or "application/x-tar",
                file_info,
            )
        finally:
            reader.close()

        _LOGGER.debug("Successfully uploaded %s (ID: %s)", filename, file_version.id_)

    @handle_b2_errors
    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup and its associated metadata file from Backblaze B2."""
        file, metadata_file = await self._find_file_and_metadata_version_by_id(
            backup_id
        )
        if not file:
            raise BackupNotFound(f"Backup {backup_id} not found")

        # Invariant: when file is not None, metadata_file is also not None
        assert metadata_file is not None

        _LOGGER.debug(
            "Deleting backup file: %s and metadata file: %s",
            file.file_name,
            metadata_file.file_name,
        )

        await self._hass.async_add_executor_job(file.delete)
        await self._hass.async_add_executor_job(metadata_file.delete)

        self._invalidate_caches(
            backup_id,
            file.file_name,
            metadata_file.file_name,
            remove_files=True,
        )

    @handle_b2_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List all backups by finding their associated metadata files in Backblaze B2."""
        async with self._backup_list_cache_lock:
            if self._backup_list_cache and self._is_cache_valid(
                self._backup_list_cache_expiration
            ):
                _LOGGER.debug("Returning backups from cache")
                return list(self._backup_list_cache.values())

            _LOGGER.debug(
                "Cache expired or empty, fetching all files from B2 to build backup list"
            )
            all_files_in_prefix = await self._get_all_files_in_prefix()

            _LOGGER.debug(
                "Files found in prefix '%s': %s",
                self._prefix,
                list(all_files_in_prefix.keys()),
            )

            # Process metadata files sequentially to avoid exhausting executor pool
            backups = {}
            for file_name, file_version in all_files_in_prefix.items():
                if file_name.endswith(METADATA_FILE_SUFFIX):
                    backup = await self._hass.async_add_executor_job(
                        self._process_metadata_file_sync,
                        file_name,
                        file_version,
                        all_files_in_prefix,
                    )
                    if backup:
                        backups[backup.backup_id] = backup
            self._backup_list_cache = backups
            self._backup_list_cache_expiration = time() + CACHE_TTL

            return list(backups.values())

    @handle_b2_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Get a specific backup by its ID from Backblaze B2."""
        if self._backup_list_cache and self._is_cache_valid(
            self._backup_list_cache_expiration
        ):
            if backup := self._backup_list_cache.get(backup_id):
                _LOGGER.debug("Returning backup %s from cache", backup_id)
                return backup

        file, metadata_file_version = await self._find_file_and_metadata_version_by_id(
            backup_id
        )
        if not file or not metadata_file_version:
            raise BackupNotFound(f"Backup {backup_id} not found")

        metadata_content = await self._hass.async_add_executor_job(
            self._download_and_parse_metadata_sync,
            metadata_file_version,
        )

        _LOGGER.debug(
            "Successfully retrieved metadata for backup ID %s from file %s",
            backup_id,
            metadata_file_version.file_name,
        )
        backup = _create_backup_from_metadata(metadata_content, file)

        if self._is_cache_valid(self._backup_list_cache_expiration):
            self._backup_list_cache[backup.backup_id] = backup

        return backup

    async def _find_file_and_metadata_version_by_id(
        self, backup_id: str
    ) -> tuple[FileVersion | None, FileVersion | None]:
        """Find the main backup file and its associated metadata file version by backup ID."""
        all_files_in_prefix = await self._get_all_files_in_prefix()

        # Process metadata files sequentially to avoid exhausting executor pool
        for file_name, file_version in all_files_in_prefix.items():
            if file_name.endswith(METADATA_FILE_SUFFIX):
                (
                    result_backup_file,
                    result_metadata_file_version,
                ) = await self._hass.async_add_executor_job(
                    self._process_metadata_file_for_id_sync,
                    file_name,
                    file_version,
                    backup_id,
                    all_files_in_prefix,
                )
                if result_backup_file and result_metadata_file_version:
                    return result_backup_file, result_metadata_file_version

        _LOGGER.debug("Backup %s not found", backup_id)
        return None, None

    def _process_metadata_file_for_id_sync(
        self,
        file_name: str,
        file_version: FileVersion,
        target_backup_id: str,
        all_files_in_prefix: dict[str, FileVersion],
    ) -> tuple[FileVersion | None, FileVersion | None]:
        """Synchronously process a single metadata file for a specific backup ID.

        Called within a thread pool executor.
        """
        try:
            download_response = file_version.download().response
        except B2Error as err:
            _LOGGER.warning(
                "Failed to download metadata file %s during ID search: %s",
                file_name,
                err,
            )
            return None, None

        try:
            metadata_content = _parse_metadata(
                download_response.content.decode("utf-8")
            )
        except ValueError:
            return None, None

        if metadata_content["backup_id"] != target_backup_id:
            _LOGGER.debug(
                "Metadata file %s does not match target backup ID %s",
                file_name,
                target_backup_id,
            )
            return None, None

        found_backup_file = _find_backup_file_for_metadata(
            file_name, all_files_in_prefix, self._prefix
        )
        if not found_backup_file:
            _LOGGER.warning(
                "Found metadata file %s for backup ID %s, but no corresponding backup file",
                file_name,
                target_backup_id,
            )
            return None, None

        _LOGGER.debug(
            "Found backup file %s and metadata file %s for ID %s",
            found_backup_file.file_name,
            file_name,
            target_backup_id,
        )
        return found_backup_file, file_version

    async def _get_all_files_in_prefix(self) -> dict[str, FileVersion]:
        """Get all file versions in the configured prefix from Backblaze B2.

        Uses a cache to minimize API calls.

        This fetches a flat list of all files, including main backups and metadata files.
        """
        async with self._all_files_cache_lock:
            if self._is_cache_valid(self._all_files_cache_expiration):
                _LOGGER.debug("Returning all files from cache")
                return self._all_files_cache

            _LOGGER.debug("Cache for all files expired or empty, fetching from B2")
            all_files_in_prefix = await self._hass.async_add_executor_job(
                self._fetch_all_files_in_prefix
            )
            self._all_files_cache = all_files_in_prefix
            self._all_files_cache_expiration = time() + CACHE_TTL
            return all_files_in_prefix

    def _fetch_all_files_in_prefix(self) -> dict[str, FileVersion]:
        """Fetch all files in the configured prefix from B2."""
        all_files: dict[str, FileVersion] = {}
        for file, _ in self._bucket.ls(self._prefix):
            all_files[file.file_name] = file
        return all_files

    def _process_metadata_file_sync(
        self,
        file_name: str,
        file_version: FileVersion,
        all_files_in_prefix: dict[str, FileVersion],
    ) -> AgentBackup | None:
        """Synchronously process a single metadata file and return an AgentBackup if valid."""
        try:
            download_response = file_version.download().response
        except B2Error as err:
            _LOGGER.warning("Failed to download metadata file %s: %s", file_name, err)
            return None

        try:
            metadata_content = _parse_metadata(
                download_response.content.decode("utf-8")
            )
        except ValueError:
            return None

        found_backup_file = _find_backup_file_for_metadata(
            file_name, all_files_in_prefix, self._prefix
        )
        if not found_backup_file:
            _LOGGER.warning(
                "Found metadata file %s but no corresponding backup file",
                file_name,
            )
            return None

        _LOGGER.debug(
            "Successfully processed metadata file %s for backup ID %s",
            file_name,
            metadata_content["backup_id"],
        )
        return _create_backup_from_metadata(metadata_content, found_backup_file)

    def _invalidate_caches(
        self,
        backup_id: str,
        tar_filename: str,
        metadata_filename: str | None,
        *,
        remove_files: bool = False,
    ) -> None:
        """Invalidate caches after upload/deletion operations.

        Args:
            backup_id: The backup ID to remove from backup cache
            tar_filename: The tar filename to remove from files cache
            metadata_filename: The metadata filename to remove from files cache
            remove_files: If True, remove specific files from cache; if False, expire entire cache
        """
        if remove_files:
            if self._is_cache_valid(self._all_files_cache_expiration):
                self._all_files_cache.pop(tar_filename, None)
                if metadata_filename:
                    self._all_files_cache.pop(metadata_filename, None)

            if self._is_cache_valid(self._backup_list_cache_expiration):
                self._backup_list_cache.pop(backup_id, None)
        else:
            # For uploads, we can't easily add new FileVersion objects without API calls,
            # so we expire the entire cache for simplicity
            self._all_files_cache_expiration = 0.0
            self._backup_list_cache_expiration = 0.0
