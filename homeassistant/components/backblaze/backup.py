"""Backup platform for the Backblaze integration."""

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import hashlib
import json
import logging
from typing import Any, cast

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
METADATA_FILE_SUFFIX = ".metadata.json"  # New constant for metadata file suffix


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
    """Return a list of backup agents."""
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


class BackblazeBackupAgent(BackupAgent):
    """Backup agent for Backblaze."""

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
        """Download a backup."""

        file, metadata_file_name = await self._find_file_and_metadata_name_by_id(
            backup_id
        )
        if file is None:
            raise BackupNotFound(f"Backup {backup_id} not found")

        _LOGGER.debug("Downloading %s", file.file_name)

        downloaded_file = await self._hass.async_add_executor_job(file.download)
        response = downloaded_file.response

        iterator = response.iter_content(chunk_size=8192)

        async def stream_buffer() -> AsyncIterator[bytes]:
            """Stream the response into an AsyncIterator."""
            while True:
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
        """Upload a backup."""

        # Prepare the metadata to be stored in a separate .json file
        # The 'file_info' for the backup file itself can be minimal or empty
        backup_file_info: dict[
            str, Any
        ] = {}  # Minimal file info for the main backup file

        # Metadata to be written to a separate JSON file
        # IMPORTANT: backup.as_dict() already returns a dictionary.
        # It should be directly stored as the 'backup_metadata' value.
        # Then the entire `metadata_content` dictionary is dumped to JSON.
        metadata_content = {
            "metadata_version": METADATA_VERSION,
            "backup_id": backup.backup_id,
            "backup_metadata": backup.as_dict(),
        }

        # You had this line: `json.dumps(metadata_content).encode("utf-8")`
        # but it wasn't assigned to anything. It's now correctly used below.

        filename = self._prefix + suggested_filename(backup)
        metadata_filename = filename + METADATA_FILE_SUFFIX

        try:
            _LOGGER.debug(
                "Uploading backup: %s, and metadata: %s", filename, metadata_filename
            )

            # --- Main Backup File Upload ---
            if backup.size < DEFAULT_MIN_PART_SIZE:
                await self._upload_simple_b2(filename, open_stream, backup_file_info)
            else:
                await self._upload_multipart_b2(filename, open_stream, backup_file_info)

            # --- Metadata File Upload ---
            metadata_content_bytes = json.dumps(metadata_content).encode("utf-8")
            _LOGGER.debug("Uploading metadata file: %s", metadata_filename)
            await self._hass.async_add_executor_job(
                lambda: self._bucket.upload_bytes(
                    metadata_content_bytes,
                    metadata_filename,
                    content_type="application/json",
                    file_info={"metadata_only": "true"},
                )
            )
            _LOGGER.debug("Metadata file upload finished for %s", metadata_filename)

        except B2Error as err:  # Assuming B2Error is defined
            _LOGGER.error("Backblaze B2 API error during backup upload: %s", err)
            raise BackupAgentError(  # Assuming BackupAgentError is defined
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

        _LOGGER.debug(
            "Uploading main backup file %s (size: %d bytes) using simple upload",
            filename,
            len(file_data),
        )

        # Use a nested def function for simple upload
        def _upload_simple_job() -> None:
            self._bucket.upload_bytes(
                bytes(file_data),
                filename,
                content_type="application/x-tar",
                file_info=file_info,
            )

        await self._hass.async_add_executor_job(_upload_simple_job)
        _LOGGER.debug("Simple upload finished for %s", filename)

    async def _upload_multipart_b2(
        self,
        filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        file_info: dict[str, Any],
    ) -> None:
        """Uploads a large file to B2 using multipart upload (streaming)."""
        _LOGGER.debug("Starting multipart upload for %s", filename)

        large_file = None

        try:
            # Step 1: Start a large file upload
            def _start_large_file_job() -> Any:
                return self._bucket.start_large_file(
                    file_name=filename,
                    content_type="application/x-tar",
                    file_info=file_info,
                )

            large_file = await self._hass.async_add_executor_job(_start_large_file_job)
            file_id = large_file.file_id

            parts: list[dict[str, Any]] = []
            part_number = 1
            buffer_size = 0
            buffer: list[bytes] = []

            stream = await open_stream()
            async for chunk in stream:
                buffer_size += len(chunk)
                buffer.append(chunk)

                if buffer_size >= DEFAULT_MIN_PART_SIZE:
                    current_part_data = b"".join(buffer)
                    current_part_number = part_number

                    _LOGGER.debug(
                        "Uploading part number %d for %s (size: %d bytes)",
                        current_part_number,
                        filename,
                        len(current_part_data),
                    )

                    # Use a nested def function for upload_part
                    def _upload_part_job(data: bytes, num: int) -> None:
                        self._bucket.upload_part(
                            file_id=file_id,
                            part_number=num,
                            data_stream=data,
                        )

                    # Pass the specific values as arguments to the _upload_part_job
                    await self._hass.async_add_executor_job(
                        functools.partial(
                            _upload_part_job, current_part_data, current_part_number
                        )
                    )

                    sha1_checksum = hashlib.sha1(current_part_data).hexdigest()
                    parts.append(
                        {
                            "partNumber": current_part_number,
                            "contentSha1": sha1_checksum,
                        }
                    )

                    part_number += 1
                    buffer_size = 0
                    buffer = []

            # Upload the final buffer as the last part
            if buffer:
                final_part_data_to_upload = b"".join(buffer)
                final_part_number_to_upload = part_number

                _LOGGER.debug(
                    "Uploading final part number %d for %s (size: %d bytes)",
                    final_part_number_to_upload,
                    filename,
                    len(final_part_data_to_upload),
                )

                # Use a nested def function for the final part upload
                def _upload_final_part_job(data: bytes, num: int) -> None:
                    self._bucket.upload_part(
                        file_id=file_id,
                        part_number=num,
                        data_stream=data,
                    )

                await self._hass.async_add_executor_job(
                    functools.partial(
                        _upload_final_part_job,
                        final_part_data_to_upload,
                        final_part_number_to_upload,
                    )
                )

                sha1_checksum = hashlib.sha1(final_part_data_to_upload).hexdigest()
                parts.append(
                    {
                        "partNumber": final_part_number_to_upload,
                        "contentSha1": sha1_checksum,
                    }
                )

            # Step 3: Finish the large file upload
            final_sha1_array = [p["contentSha1"] for p in parts]

            def _finish_large_file_job(sha1s: list[str]) -> None:
                self._bucket.finish_large_file(
                    file_id=file_id,
                    part_sha1_array=sha1s,
                )

            await self._hass.async_add_executor_job(
                functools.partial(_finish_large_file_job, final_sha1_array)
            )
            _LOGGER.debug("Multipart upload finished for %s", filename)

        except Exception:
            if large_file:
                try:
                    _LOGGER.warning("Aborting multipart upload for %s", filename)

                    def _cancel_large_file_job(file_id_to_cancel: str) -> None:
                        self._bucket.cancel_large_file(file_id_to_cancel)

                    await self._hass.async_add_executor_job(
                        functools.partial(_cancel_large_file_job, file_id)
                    )
                except Exception:
                    _LOGGER.exception(
                        "Failed to abort multipart upload for %s", filename
                    )
            raise

    @handle_b2_errors
    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup and its associated metadata file."""
        file, metadata_file_name = await self._find_file_and_metadata_name_by_id(
            backup_id
        )
        if file is None:
            raise BackupNotFound(f"Backup {backup_id} not found")

        _LOGGER.debug(
            "Deleting backup file: %s and metadata file: %s",
            file.file_name,
            metadata_file_name,
        )

        # Delete the main backup file
        await self._hass.async_add_executor_job(file.delete)

        # Attempt to find and delete the metadata file as well
        def delete_metadata_file_sync() -> None:
            try:
                # Find the metadata file by its name (which was constructed from the backup file name)
                # B2SDK's ls returns [file, folder] tuples, we only care about files here.
                metadata_files = [
                    f
                    for f, _ in self._bucket.ls(metadata_file_name)
                    if f.file_name == metadata_file_name
                ]
                if metadata_files:
                    metadata_files[0].delete()
                else:
                    _LOGGER.warning(
                        "Metadata file %s not found for deletion", metadata_file_name
                    )
            except B2Error as err:
                _LOGGER.error(
                    "Failed to delete metadata file %s: %s", metadata_file_name, err
                )

        await self._hass.async_add_executor_job(delete_metadata_file_sync)

    @handle_b2_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List all backups by finding their metadata files."""
        backups: list[AgentBackup] = []
        all_files_in_prefix = await self._get_all_files_in_prefix()

        _LOGGER.debug(
            "Files found in prefix '%s': %s",
            self._prefix,
            list(all_files_in_prefix.keys()),
        )

        # Collect tasks for concurrent metadata downloads
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

        # Run metadata downloads concurrently
        results = await asyncio.gather(*tasks)
        backups = [backup for backup in results if backup]

        _LOGGER.debug("Found %d backups", len(backups))
        return backups

    @handle_b2_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Get a backup by finding its metadata file and then constructing the AgentBackup."""
        file, metadata_file_name = await self._find_file_and_metadata_name_by_id(
            backup_id
        )
        if file is None or metadata_file_name is None:
            raise BackupNotFound(f"Backup {backup_id} not found")

        # Download and parse the metadata file
        def download_metadata_sync() -> dict[str, Any]:
            metadata_b2_file = None
            for [f, _] in self._bucket.ls(metadata_file_name):
                if f.file_name == metadata_file_name:
                    metadata_b2_file = f
                    break
            if metadata_b2_file is None:
                raise BackupNotFound(f"Metadata file for backup {backup_id} not found")

            downloaded_meta = metadata_b2_file.download()
            # FIX 1: Read and decode content from DownloadedFile object
            metadata_bytes = downloaded_meta.response.content
            return cast(dict[str, Any], json.loads(metadata_bytes.decode("utf-8")))

        metadata_content = await self._hass.async_add_executor_job(
            download_metadata_sync
        )

        return self._backup_from_b2_metadata(metadata_content, file)

    async def _find_file_and_metadata_name_by_id(
        self, backup_id: str
    ) -> tuple[FileVersion | None, str | None]:
        """Find the main backup file and determine its associated metadata file name by backup ID."""
        all_files_in_prefix = await self._get_all_files_in_prefix()

        # Collect tasks for concurrent metadata downloads
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
        for result_backup_file, result_metadata_file_name in results:
            if result_backup_file and result_metadata_file_name:
                return result_backup_file, result_metadata_file_name

        _LOGGER.debug("Backup %s not found", backup_id)
        return None, None

    def _process_metadata_file_for_id_sync(
        self,
        file_name: str,
        file_version: FileVersion,
        target_backup_id: str,
        all_files_in_prefix: dict[str, FileVersion],
    ) -> tuple[FileVersion | None, str | None]:
        """Synchronously process a single metadata file for a specific backup ID."""
        try:
            downloaded_meta = file_version.download()
            # FIX 2: Read and decode content from DownloadedFile object
            metadata_bytes = downloaded_meta.response.content
            metadata_content = json.loads(metadata_bytes.decode("utf-8"))
            # json.loads(downloaded_meta.text_content) # Old line

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and metadata_content.get("backup_id") == target_backup_id
            ):
                found_metadata_file_name = file_name
                found_backup_file = next(
                    (
                        archive_file_version
                        for archive_file_name, archive_file_version in all_files_in_prefix.items()
                        if archive_file_name
                        == found_metadata_file_name.removesuffix(METADATA_FILE_SUFFIX)
                        and not archive_file_name.endswith(METADATA_FILE_SUFFIX)
                    ),
                    None,
                )
                if found_backup_file:
                    _LOGGER.debug(
                        "Found backup file %s and metadata file %s from id %s",
                        found_backup_file.file_name,
                        found_metadata_file_name,
                        target_backup_id,
                    )
                    return found_backup_file, found_metadata_file_name
                _LOGGER.warning(
                    "Found metadata file %s for backup ID %s, but no corresponding backup file",
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
        metadata = metadata_content["backup_metadata"]  # This is now the dict directly
        metadata["size"] = backup_file.size
        # metadata["name"] = backup_file.file_name # This line is commented out, keep it that way if intentional
        return AgentBackup.from_dict(metadata)

    async def _get_all_files_in_prefix(self) -> dict[str, FileVersion]:
        """Get all files in the configured prefix."""
        all_files_in_prefix: dict[str, FileVersion] = {}

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
        """Synchronously process a single metadata file and return an AgentBackup if valid."""
        try:
            downloaded_meta = file_version.download()
            # FIX 3: Read and decode content from DownloadedFile object
            metadata_bytes = downloaded_meta.response.content
            metadata_content = json.loads(metadata_bytes.decode("utf-8"))
            # json.loads(downloaded_meta.text_content) # Old line

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and "backup_id" in metadata_content
                and "backup_metadata" in metadata_content
            ):
                # Correctly extract the backup ID from the filename.
                # Assuming filename is like "prefix/backup_id_timestamp.tar.metadata.json"
                # so backup_id needs to exclude the .tar.metadata.json part too.
                # The provided example `HA_Test/Test33_2025-07-27_20.17_21911471.tar.metadata.json`
                # suggests backup_id is "Test33_2025-07-27_20.17_21911471"
                # So we need to strip .tar.metadata.json AND the prefix.
                base_file_name = file_name[
                    len(self._prefix) : -len(METADATA_FILE_SUFFIX)
                ]
                # Then remove the .tar suffix if present
                if base_file_name.endswith(".tar"):
                    backup_id = base_file_name[: -len(".tar")]
                else:
                    backup_id = base_file_name  # Fallback if .tar isn't there, though it should be

                found_backup_archive_file = None

                for (
                    archive_file_name,
                    archive_file_version,
                ) in all_files_in_prefix.items():
                    # Check if the archive file name starts with the prefix + derived backup_id
                    # and is not a metadata file itself
                    if archive_file_name.startswith(
                        self._prefix + backup_id
                    ) and not archive_file_name.endswith(METADATA_FILE_SUFFIX):
                        found_backup_archive_file = archive_file_version
                        _LOGGER.debug(
                            "Matched metadata file '%s' with archive file '%s'",
                            file_name,
                            archive_file_name,
                        )
                        break
                if found_backup_archive_file:
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
