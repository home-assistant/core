"""Backup platform for the Backblaze integration."""

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import json
import logging
import mimetypes
import os
import tempfile
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
from .const import CONF_PREFIX, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
METADATA_VERSION = "1"
METADATA_FILE_SUFFIX = ".metadata.json"


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

    @handle_b2_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup from Backblaze B2."""

        file, metadata_file = await self._find_file_and_metadata_version_by_id(
            backup_id
        )
        if file is None:
            raise BackupNotFound(f"Backup {backup_id} not found")

        _LOGGER.debug("Downloading %s", file.file_name)

        # File download is a synchronous (blocking) operation, so run in executor.
        downloaded_file = await self._hass.async_add_executor_job(file.download)
        response = downloaded_file.response

        # B2 SDK's response.iter_content is blocking, so stream it chunk by chunk
        # within the executor.
        iterator = response.iter_content(chunk_size=8192)

        async def stream_buffer() -> AsyncIterator[bytes]:
            """Stream the response into an AsyncIterator."""
            while True:
                # Call next() within the executor to avoid blocking the event loop.
                chunk = await self._hass.async_add_executor_job(next, iterator, None)
                if chunk is None:
                    break
                yield chunk

        return stream_buffer()

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

        # Prepare file_info for the main backup file (can be minimal).
        backup_file_info: dict[str, Any] = {}

        # Prepare metadata content for the separate JSON file.
        # backup.as_dict() already returns a dictionary, which is directly used here.
        metadata_content = {
            "metadata_version": METADATA_VERSION,
            "backup_id": backup.backup_id,
            "backup_metadata": backup.as_dict(),
        }

        filename = self._prefix + suggested_filename(backup)
        metadata_filename = filename + METADATA_FILE_SUFFIX

        try:
            _LOGGER.debug(
                "Uploading backup: %s, and metadata: %s", filename, metadata_filename
            )

            # --- Main Backup File Upload ---
            # Use simple upload for small files, multipart for larger ones.
            if backup.size < DEFAULT_MIN_PART_SIZE:
                await self._upload_simple_b2(filename, open_stream, backup_file_info)
            else:
                await self._upload_multipart_b2(filename, open_stream, backup_file_info)

            _LOGGER.info("Main backup file upload finished for %s", filename)

            # --- Metadata File Upload ---
            # The metadata file is uploaded as a single byte string.
            metadata_content_bytes = json.dumps(metadata_content).encode("utf-8")
            _LOGGER.info("Uploading metadata file: %s", metadata_filename)
            await self._hass.async_add_executor_job(
                lambda: self._bucket.upload_bytes(
                    metadata_content_bytes,
                    metadata_filename,
                    content_type="application/json",
                    file_info={
                        "metadata_only": "true"
                    },  # Custom info for identification
                )
            )
            _LOGGER.info("Metadata file upload finished for %s", metadata_filename)

        except B2Error as err:
            _LOGGER.error("Backblaze B2 API error during backup upload: %s", err)
            # Attempt to clean up the main backup file if metadata upload failed,
            # to prevent orphaned files.
            _LOGGER.warning(
                "Attempting to delete partially uploaded main backup file %s due to metadata upload failure",
                filename,
            )
            try:
                # Retrieve the file info to get the FileVersion object for deletion.
                uploaded_main_file_info = await self._hass.async_add_executor_job(
                    self._bucket.get_file_info_by_name, filename
                )
                await self._hass.async_add_executor_job(uploaded_main_file_info.delete)
                _LOGGER.info(
                    "Successfully deleted partially uploaded main backup file %s",
                    filename,
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to clean up partially uploaded main backup file %s:",
                    filename,
                )
                _LOGGER.exception(
                    "Manual intervention may be required to delete %s from Backblaze B2",
                    filename,
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
            _LOGGER.info("Backup upload complete: %s", filename)

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

        _LOGGER.info(
            "Uploading main backup file %s (size: %d bytes) using simple upload",
            filename,
            len(file_data),
        )

        # Run the synchronous upload_bytes call in the executor.
        def _upload_simple_job() -> None:
            self._bucket.upload_bytes(
                bytes(file_data),  # Convert bytearray to bytes
                filename,
                content_type="application/x-tar",
                file_info=file_info,
            )

        await self._hass.async_add_executor_job(_upload_simple_job)
        _LOGGER.info("Simple upload finished for %s", filename)

    async def _upload_multipart_b2(
        self,
        filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        file_info: dict[str, Any],
    ) -> None:
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
                if hasattr(stream_to_disk, "aclose") and callable(
                    stream_to_disk.aclose
                ):
                    await stream_to_disk.aclose()
                elif hasattr(stream_to_disk, "close") and callable(
                    stream_to_disk.close
                ):
                    stream_to_disk.close()

            def _upload_local_file_job() -> FileVersion:
                content_type, _ = mimetypes.guess_type(filename)
                return self._bucket.upload_local_file(
                    local_file=temp_file_path,
                    file_name=filename,
                    content_type=content_type or "application/octet-stream",
                    file_info=file_info,
                )

            file_version = await self._hass.async_add_executor_job(
                _upload_local_file_job
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
        if file is None:
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

            def delete_metadata_file_sync() -> None:
                try:
                    metadata_file.delete()
                except B2Error as err:
                    _LOGGER.error(
                        "Failed to delete metadata file %s: %s",
                        metadata_file.file_name,
                        err,
                    )
                    raise

            try:
                await self._hass.async_add_executor_job(delete_metadata_file_sync)
            except B2Error:
                _LOGGER.error("B2Error propagated from executor for metadata")
                raise
            except (
                Exception
            ) as e:  # <--- Catch any other unexpected executor exceptions
                _LOGGER.error("Unexpected error from executor for metadata: %s", e)
                raise BackupAgentError(
                    "Unexpected error in metadata deletion"
                ) from e  # Convert to BackupAgentError
        else:
            _LOGGER.warning(
                "Metadata file for backup %s not found for deletion", backup_id
            )

    @handle_b2_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List all backups by finding their associated metadata files in Backblaze B2."""
        backups: list[AgentBackup] = []
        all_files_in_prefix = await self._get_all_files_in_prefix()

        _LOGGER.debug(
            "Files found in prefix '%s': %s",
            self._prefix,
            list(all_files_in_prefix.keys()),
        )

        # Collect tasks for concurrent metadata file processing.
        tasks = []
        for file_name, file_version in all_files_in_prefix.items():
            if file_name.endswith(METADATA_FILE_SUFFIX):
                tasks.append(
                    self._hass.async_add_executor_job(
                        self._process_metadata_file_sync,
                        file_name,
                        file_version,
                        all_files_in_prefix,
                    )
                )

        # Run metadata downloads and parsing concurrently.
        results = await asyncio.gather(*tasks)
        backups = [backup for backup in results if backup]

        _LOGGER.debug("Found %d backups", len(backups))
        return backups

    @handle_b2_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Get a specific backup by its ID from Backblaze B2."""
        file, metadata_file_version = await self._find_file_and_metadata_version_by_id(
            backup_id
        )
        if file is None or metadata_file_version is None:
            raise BackupNotFound(f"Backup {backup_id} not found")

        # Download and parse the metadata file synchronously in the executor.
        def _download_metadata_sync_job() -> dict[str, Any]:
            downloaded_meta = metadata_file_version.download()
            metadata_bytes = downloaded_meta.response.content
            return cast(dict[str, Any], json.loads(metadata_bytes.decode("utf-8")))

        metadata_content = await self._hass.async_add_executor_job(
            _download_metadata_sync_job
        )

        _LOGGER.debug(
            "Successfully retrieved metadata for backup ID %s from file %s",
            backup_id,
            metadata_file_version.file_name,
        )
        return self._backup_from_b2_metadata(metadata_content, file)

    async def _find_file_and_metadata_version_by_id(
        self, backup_id: str
    ) -> tuple[FileVersion | None, FileVersion | None]:
        """Find the main backup file and its associated metadata file version by backup ID.

        Scans all files within the configured prefix and concurrently checks metadata files.
        """
        all_files_in_prefix = await self._get_all_files_in_prefix()

        tasks = []
        for file_name, file_version in all_files_in_prefix.items():
            if file_name.endswith(METADATA_FILE_SUFFIX):
                tasks.append(
                    self._hass.async_add_executor_job(
                        self._process_metadata_file_for_id_sync,
                        file_name,
                        file_version,
                        backup_id,
                        all_files_in_prefix,
                    )
                )

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
            downloaded_meta = file_version.download()
            metadata_bytes = downloaded_meta.response.content
            metadata_content = json.loads(metadata_bytes.decode("utf-8"))

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and metadata_content.get("backup_id") == target_backup_id
            ):
                # Construct the expected main backup file name from the metadata file.
                found_metadata_file_name = file_name
                base_name = found_metadata_file_name.removesuffix(METADATA_FILE_SUFFIX)
                expected_backup_file_prefix = base_name

                # Search for the corresponding main backup file.
                # It should start with the base name of the metadata file and end with '.tar'.
                found_backup_file = next(
                    (
                        archive_file_version
                        for archive_file_name, archive_file_version in all_files_in_prefix.items()
                        if archive_file_name.startswith(expected_backup_file_prefix)
                        and archive_file_name.endswith(".tar")
                    ),
                    None,
                )
                if found_backup_file:
                    _LOGGER.debug(
                        "Found backup file %s and metadata file %s for ID %s",
                        found_backup_file.file_name,
                        found_metadata_file_name,
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
        # The 'name' attribute for AgentBackup is typically derived from the backup_id within Home Assistant.
        # No need to set it from file_name here unless specific requirements dictate.
        # metadata["name"] = backup_file.file_name
        return AgentBackup.from_dict(metadata)

    async def _get_all_files_in_prefix(self) -> dict[str, FileVersion]:
        """Get all file versions in the configured prefix from Backblaze B2.

        This fetches a flat list of all files, including main backups and metadata files.
        """
        all_files_in_prefix: dict[str, FileVersion] = {}

        # The bucket.ls operation is synchronous and can be slow for many files.
        def get_files_sync() -> None:
            for [file, _] in self._bucket.ls(self._prefix):
                all_files_in_prefix[file.file_name] = file

        await self._hass.async_add_executor_job(get_files_sync)
        return all_files_in_prefix

    def _process_metadata_file_sync(
        self,
        file_name: str,
        file_version: FileVersion,
        all_files_in_prefix: dict[str, FileVersion],
    ) -> AgentBackup | None:
        """Synchronously process a single metadata file and return an AgentBackup if valid.

        Called within a thread pool executor for concurrent processing of metadata files.
        """
        try:
            downloaded_meta = file_version.download()
            metadata_bytes = downloaded_meta.response.content
            metadata_content = json.loads(metadata_bytes.decode("utf-8"))

            # Validate metadata structure and version.
            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and "backup_id" in metadata_content
                and "backup_metadata" in metadata_content
            ):
                # Derive the expected main backup file name from the metadata file name.
                # Remove the prefix and the metadata suffix.
                base_file_name = file_name[
                    len(self._prefix) : -len(METADATA_FILE_SUFFIX)
                ]
                # Further remove the .tar suffix if present, to get the raw backup_id part.
                if base_file_name.endswith(".tar"):
                    backup_id = base_file_name[: -len(".tar")]
                else:
                    # Fallback for unexpected naming, though .tar should always be there.
                    backup_id = base_file_name

                found_backup_archive_file = None

                # Find the corresponding main backup archive file.
                for (
                    archive_file_name,
                    archive_file_version,
                ) in all_files_in_prefix.items():
                    if (
                        archive_file_name.startswith(self._prefix + backup_id)
                        and archive_file_name.endswith(".tar")
                        and archive_file_name
                        != file_name  # Ensure it's not the metadata file itself
                    ):
                        found_backup_archive_file = archive_file_version
                        _LOGGER.debug(
                            "Matched metadata file '%s' with archive file '%s'",
                            file_name,
                            archive_file_name,
                        )
                        break

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
                    backup_id,
                )
            else:
                _LOGGER.debug("Skipping non-conforming metadata file: %s", file_name)

        except (B2Error, json.JSONDecodeError) as err:
            _LOGGER.warning("Failed to parse metadata file %s: %s", file_name, err)
        return None
