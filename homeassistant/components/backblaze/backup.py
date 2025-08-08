"""Backup platform for the Backblaze integration."""

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import json
import logging
import mimetypes
import os
import tempfile
from time import time  # Import time for caching
from typing import Any, cast

import aiofiles
from b2sdk.v2 import DEFAULT_MIN_PART_SIZE, FileVersion
from b2sdk.v2.exception import B2Error

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

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
    """Return a list of backup agents for all configured Backblaze entries."""
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
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


class BackblazeBackupAgent(BackupAgent):
    """Backup agent for Backblaze B2 cloud storage."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: BackblazeConfigEntry) -> None:
        """Initialize the Backblaze agent."""
        super().__init__()
        self._hass = hass
        self._bucket = entry.runtime_data
        self._prefix = entry.data[CONF_PREFIX]

        self.name = entry.title
        self.unique_id = entry.entry_id

        # Caching for _get_all_files_in_prefix and async_list_backups
        self._all_files_cache: dict[str, FileVersion] = {}
        self._all_files_cache_expiration: float = 0.0
        self._backup_list_cache: dict[str, AgentBackup] = {}
        self._backup_list_cache_expiration: float = 0.0

    @handle_b2_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup from Backblaze B2."""
        file, _ = await self._find_file_and_metadata_version_by_id(backup_id)
        if not file:
            raise BackupNotFound(f"Backup {backup_id} not found")

        _LOGGER.debug("Downloading %s", file.file_name)

        # File download is a synchronous (blocking) operation, so run in executor.
        downloaded_file = await self._hass.async_add_executor_job(file.download)
        response = downloaded_file.response

        async def stream_buffer_and_close() -> AsyncIterator[bytes]:
            """Stream the response into an AsyncIterator and ensure closure."""
            try:
                # B2 SDK's response.iter_content is blocking, so stream it chunk by chunk
                # within the executor.
                iterator = response.iter_content(chunk_size=8192)
                while True:
                    chunk = await self._hass.async_add_executor_job(
                        next, iterator, None
                    )
                    if chunk is None:
                        break
                    yield chunk
            finally:
                _LOGGER.debug("Closing download stream for %s", file.file_name)
                # Ensure the underlying response stream is closed
                if hasattr(response, "close") and callable(response.close):
                    await self._hass.async_add_executor_job(response.close)

        return stream_buffer_and_close()

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

        try:
            # --- Main Backup File Upload ---
            if backup.size < DEFAULT_MIN_PART_SIZE:
                await self._upload_simple_b2(prefixed_tar_filename, open_stream, {})
            else:
                await self._upload_multipart_b2(prefixed_tar_filename, open_stream, {})
            _LOGGER.info(
                "Main backup file upload finished for %s", prefixed_tar_filename
            )

            # --- Metadata File Upload ---
            _LOGGER.info("Uploading metadata file: %s", prefixed_metadata_filename)
            await self._hass.async_add_executor_job(
                lambda: self._bucket.upload_bytes(
                    metadata_content_bytes,
                    prefixed_metadata_filename,
                    content_type="application/json",
                    file_info={"metadata_only": "true"},
                )
            )
            _LOGGER.info(
                "Metadata file upload finished for %s", prefixed_metadata_filename
            )

        except B2Error as err:
            _LOGGER.error("Backblaze B2 API error during backup upload: %s", err)
            _LOGGER.warning(
                "Attempting to delete partially uploaded main backup file %s due to metadata upload failure",
                prefixed_tar_filename,
            )
            try:
                # Get file info to obtain fileId for deletion
                uploaded_main_file_info = await self._hass.async_add_executor_job(
                    self._bucket.get_file_info_by_name, prefixed_tar_filename
                )
                await self._hass.async_add_executor_job(uploaded_main_file_info.delete)
                _LOGGER.info(
                    "Successfully deleted partially uploaded main backup file %s",
                    prefixed_tar_filename,
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to clean up partially uploaded main backup file %s due to unexpected error:",
                    prefixed_tar_filename,
                )
                _LOGGER.exception(
                    "Manual intervention may be required to delete %s from Backblaze B2",
                    prefixed_tar_filename,
                )
            raise BackupAgentError(
                f"Failed to upload backup to Backblaze B2: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception("An unexpected error occurred during backup upload")
            raise BackupAgentError(
                f"An unexpected error occurred during backup upload: {err}"
            ) from err
        else:
            _LOGGER.info("Backup upload complete: %s", prefixed_tar_filename)
            # Invalidate the cache after a successful upload
            self._all_files_cache_expiration = 0.0
            self._backup_list_cache_expiration = 0.0

    async def _upload_simple_b2(
        self,
        filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        file_info: dict[str, Any],
    ) -> None:
        """Uploads a small file to B2 using a simple single-call upload."""
        _LOGGER.debug("Reading entire backup stream into memory for %s", filename)
        stream = await open_stream()
        file_data = bytearray()
        async for chunk in stream:
            file_data.extend(chunk)

        # Explicitly close the stream after reading all content
        if hasattr(stream, "aclose") and callable(stream.aclose):
            await stream.aclose()

        _LOGGER.info(
            "Uploading main backup file %s (size: %d bytes) using simple upload",
            filename,
            len(file_data),
        )

        await self._hass.async_add_executor_job(
            lambda: self._bucket.upload_bytes(
                bytes(file_data),
                filename,
                content_type="application/x-tar",
                file_info=file_info,
            )
        )
        _LOGGER.info("Simple upload finished for %s", filename)

    async def _upload_multipart_b2(
        self,
        filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        file_info: dict[str, Any],
    ) -> None:
        """Uploads a large file to B2 using multipart upload via a temporary file."""
        temp_file_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
                temp_file_path = tmp.name

            stream_to_disk = await open_stream()
            try:
                async with aiofiles.open(temp_file_path, mode="wb") as f:
                    async for chunk in stream_to_disk:
                        await f.write(chunk)
            finally:
                # Explicitly close the stream after writing to disk
                if hasattr(stream_to_disk, "aclose") and callable(
                    stream_to_disk.aclose
                ):
                    await stream_to_disk.aclose()
                elif hasattr(stream_to_disk, "close") and callable(
                    stream_to_disk.close
                ):
                    stream_to_disk.close()

            content_type, _ = mimetypes.guess_type(filename)
            file_version = await self._hass.async_add_executor_job(
                lambda: self._bucket.upload_local_file(
                    local_file=temp_file_path,
                    file_name=filename,
                    content_type=content_type or "application/octet-stream",
                    file_info=file_info,
                )
            )
            _LOGGER.info(
                "Successfully uploaded %s (ID: %s)", filename, file_version.id_
            )

        except B2Error:
            _LOGGER.exception("B2 connection error during upload for %s", filename)
            raise
        except Exception:
            _LOGGER.exception("An error occurred during upload for %s:", filename)
            raise
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError as e:
                    _LOGGER.warning(
                        "Failed to delete temporary file %s: %s", temp_file_path, e
                    )

    @handle_b2_errors
    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup and its associated metadata file from Backblaze B2."""
        file, metadata_file = await self._find_file_and_metadata_version_by_id(
            backup_id
        )
        if not file:
            raise BackupNotFound(f"Backup {backup_id} not found")

        _LOGGER.debug(
            "Deleting backup file: %s and metadata file: %s",
            file.file_name,
            metadata_file.file_name if metadata_file else "None",
        )

        # Delete the main backup file.
        await self._hass.async_add_executor_job(file.delete)

        # Attempt to delete the metadata file if it exists.
        if metadata_file:
            try:
                await self._hass.async_add_executor_job(metadata_file.delete)
            except B2Error as err:
                _LOGGER.error(
                    "Failed to delete metadata file %s: %s",
                    metadata_file.file_name,
                    err,
                )
                raise
            except Exception as e:
                _LOGGER.error("Unexpected error from executor for metadata: %s", e)
                raise BackupAgentError("Unexpected error in metadata deletion") from e
        else:
            _LOGGER.warning(
                "Metadata file for backup %s not found for deletion", backup_id
            )

        # Invalidate the cache after a successful deletion
        self._all_files_cache_expiration = 0.0
        self._backup_list_cache_expiration = 0.0

    @handle_b2_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List all backups by finding their associated metadata files in Backblaze B2."""
        if self._backup_list_cache and time() <= self._backup_list_cache_expiration:
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

        # Collect tasks for concurrent metadata file processing.
        tasks = [
            self._hass.async_add_executor_job(
                self._process_metadata_file_sync,
                file_name,
                file_version,
                all_files_in_prefix,
            )
            for file_name, file_version in all_files_in_prefix.items()
            if file_name.endswith(METADATA_FILE_SUFFIX)
        ]

        # Run metadata downloads and parsing concurrently.
        results = await asyncio.gather(*tasks)

        # Filter out None results and store in cache
        backups = {backup.backup_id: backup for backup in results if backup}
        self._backup_list_cache = backups
        self._backup_list_cache_expiration = time() + CACHE_TTL

        return list(backups.values())

    @handle_b2_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Get a specific backup by its ID from Backblaze B2."""
        # Check cache first for individual backup
        if self._backup_list_cache and time() <= self._backup_list_cache_expiration:
            if backup := self._backup_list_cache.get(backup_id):
                _LOGGER.debug("Returning backup %s from cache", backup_id)
                return backup
            # If not in cache, proceed to fetch directly to avoid full re-list if only one item is needed

        file, metadata_file_version = await self._find_file_and_metadata_version_by_id(
            backup_id
        )
        if not file or not metadata_file_version:
            raise BackupNotFound(f"Backup {backup_id} not found")

        metadata_content = await self._hass.async_add_executor_job(
            lambda: cast(
                dict[str, Any],
                json.loads(
                    metadata_file_version.download().response.content.decode("utf-8")
                ),
            )
        )

        _LOGGER.debug(
            "Successfully retrieved metadata for backup ID %s from file %s",
            backup_id,
            metadata_file_version.file_name,
        )
        backup = self._backup_from_b2_metadata(metadata_content, file)

        # Update single item in cache if found via direct get
        if time() <= self._backup_list_cache_expiration:
            self._backup_list_cache[backup.backup_id] = backup

        return backup

    async def _find_file_and_metadata_version_by_id(
        self, backup_id: str
    ) -> tuple[FileVersion | None, FileVersion | None]:
        """Find the main backup file and its associated metadata file version by backup ID."""
        all_files_in_prefix = await self._get_all_files_in_prefix()

        tasks = [
            self._hass.async_add_executor_job(
                self._process_metadata_file_for_id_sync,
                file_name,
                file_version,
                backup_id,
                all_files_in_prefix,
            )
            for file_name, file_version in all_files_in_prefix.items()
            if file_name.endswith(METADATA_FILE_SUFFIX)
        ]

        results = await asyncio.gather(*tasks)
        # Return the first matching backup and metadata file found.
        for result_backup_file, result_metadata_file_version in results:
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
            # Explicitly close the download response for metadata file in executor
            download_response = file_version.download().response
            try:
                metadata_content = json.loads(download_response.content.decode("utf-8"))
            finally:
                if hasattr(download_response, "close") and callable(
                    download_response.close
                ):
                    download_response.close()

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and metadata_content.get("backup_id") == target_backup_id
            ):
                base_name = file_name.removesuffix(METADATA_FILE_SUFFIX)
                expected_backup_file_prefix = base_name

                found_backup_file = next(
                    (
                        archive_file_version
                        for archive_file_name, archive_file_version in all_files_in_prefix.items()
                        if archive_file_name.startswith(expected_backup_file_prefix)
                        and archive_file_name.endswith(".tar")
                        and archive_file_name
                        != file_name  # Ensure we don't accidentally match the metadata file if it somehow ends with .tar
                    ),
                    None,
                )
                if found_backup_file:
                    _LOGGER.debug(
                        "Found backup file %s and metadata file %s for ID %s",
                        found_backup_file.file_name,
                        file_name,
                        target_backup_id,
                    )
                    return found_backup_file, file_version
                _LOGGER.warning(
                    "Found metadata file %s for backup ID %s, but no corresponding backup file",
                    file_name,
                    target_backup_id,
                )
            _LOGGER.debug(
                "Metadata file %s does not match target backup ID %s or version",
                file_name,
                target_backup_id,
            )
        except (B2Error, json.JSONDecodeError) as err:
            _LOGGER.warning(
                "Failed to parse metadata file %s during ID search: %s",
                file_name,
                err,
            )
        return None, None

    def _backup_from_b2_metadata(
        self, metadata_content: dict[str, Any], backup_file: FileVersion
    ) -> AgentBackup:
        """Construct an AgentBackup from parsed metadata content and the associated backup file."""
        metadata = metadata_content["backup_metadata"]
        metadata["size"] = backup_file.size
        return AgentBackup.from_dict(metadata)

    async def _get_all_files_in_prefix(self) -> dict[str, FileVersion]:
        """Get all file versions in the configured prefix from Backblaze B2.

        Uses a cache to minimize API calls.

        This fetches a flat list of all files, including main backups and metadata files.
        """
        if time() <= self._all_files_cache_expiration:
            _LOGGER.debug("Returning all files from cache")
            return self._all_files_cache

        _LOGGER.debug("Cache for all files expired or empty, fetching from B2")
        all_files_in_prefix: dict[str, FileVersion] = {}
        await self._hass.async_add_executor_job(
            lambda: [
                all_files_in_prefix.update({file.file_name: file})
                for file, _ in self._bucket.ls(self._prefix)
            ]
        )
        self._all_files_cache = all_files_in_prefix
        self._all_files_cache_expiration = time() + CACHE_TTL
        return all_files_in_prefix

    def _process_metadata_file_sync(
        self,
        file_name: str,
        file_version: FileVersion,
        all_files_in_prefix: dict[str, FileVersion],
    ) -> AgentBackup | None:
        """Synchronously process a single metadata file and return an AgentBackup if valid."""
        try:
            # Explicitly close the download response for metadata file in executor
            download_response = file_version.download().response
            try:
                metadata_content = json.loads(download_response.content.decode("utf-8"))
            finally:
                if hasattr(download_response, "close") and callable(
                    download_response.close
                ):
                    download_response.close()

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and "backup_id" in metadata_content
                and "backup_metadata" in metadata_content
            ):
                # Derive the expected main backup file name from the metadata file name.
                # Remove prefix and then the .metadata.json suffix to get base name
                base_filename_without_prefix = file_name[
                    len(self._prefix) :
                ].removesuffix(METADATA_FILE_SUFFIX)

                found_backup_archive_file = next(
                    (
                        archive_file_version
                        for archive_file_name, archive_file_version in all_files_in_prefix.items()
                        if archive_file_name.startswith(
                            self._prefix + base_filename_without_prefix
                        )
                        and archive_file_name.endswith(".tar")
                        and archive_file_name
                        != file_name  # Ensure it's not the metadata file itself
                    ),
                    None,
                )

                if found_backup_archive_file:
                    _LOGGER.debug(
                        "Successfully processed metadata file %s for backup ID %s",
                        file_name,
                        metadata_content["backup_id"],
                    )
                    return self._backup_from_b2_metadata(
                        metadata_content, found_backup_archive_file
                    )
                _LOGGER.warning(
                    "Found metadata file %s but no corresponding backup file starting with %s (after prefix)",
                    file_name,
                    base_filename_without_prefix,
                )
            else:
                _LOGGER.debug("Skipping non-conforming metadata file: %s", file_name)

        except (B2Error, json.JSONDecodeError) as err:
            _LOGGER.warning("Failed to parse metadata file %s: %s", file_name, err)
        return None
