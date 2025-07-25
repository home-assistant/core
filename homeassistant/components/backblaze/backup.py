"""Backup platform for the Backblaze integration."""

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import json
import logging
import os
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
        metadata_content = {
            "metadata_version": METADATA_VERSION,
            "backup_id": backup.backup_id,
            "backup_metadata": backup.as_dict(),  # Store the dict directly, not a string
        }
        metadata_json_str = json.dumps(metadata_content).encode("utf-8")

        filename = self._prefix + suggested_filename(backup)
        metadata_filename = filename + METADATA_FILE_SUFFIX

        _LOGGER.debug(
            "Uploading backup: %s, and metadata: %s", filename, metadata_filename
        )

        stream: AsyncIterator[bytes] = await open_stream()

        # Create pipes for both the backup file and the metadata file
        r_fd_backup, w_fd_backup = os.pipe()
        r_fd_metadata, w_fd_metadata = os.pipe()

        async def backup_writer() -> None:
            """Write async stream to the backup file pipe."""
            with os.fdopen(w_fd_backup, "wb") as w:
                async for chunk in stream:
                    w.write(chunk)
                w.close()

        def metadata_writer() -> None:
            """Write metadata JSON to the metadata file pipe."""
            with os.fdopen(w_fd_metadata, "wb") as w:
                w.write(metadata_json_str)
                w.close()

        # Schedule the writers
        backup_writer_task = self._hass.async_create_task(backup_writer())
        metadata_writer_task = self._hass.async_add_executor_job(metadata_writer)

        # The upload_files function needs to be async because it's called with await
        # and it contains await calls inside (e.g., await backup_writer_task).
        # The @handle_b2_errors decorator expects a Coroutine, so this aligns.
        @handle_b2_errors
        async def upload_files() -> None:
            # Upload the backup file
            with os.fdopen(r_fd_backup, "rb") as r:
                self._bucket.upload_unbound_stream(
                    r,
                    filename,
                    file_info=backup_file_info,  # Use minimal file_info here
                )
            # Upload the metadata file
            with os.fdopen(r_fd_metadata, "rb") as r_meta:
                self._bucket.upload_unbound_stream(
                    r_meta,
                    metadata_filename,
                    file_info={  # Add a small identifying info to the metadata file's info
                        "is_metadata_file": "true",
                        "metadata_for_file": os.path.basename(filename),
                    },
                )

        # Await the upload_files coroutine directly since it's now async
        await upload_files()
        # Ensure all tasks complete
        await backup_writer_task
        await metadata_writer_task

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
            return json.loads(downloaded_meta.text_content)  # type: ignore[no-any-return]

        metadata_content = await self._hass.async_add_executor_job(
            download_metadata_sync
        )

        return self._backup_from_b2_metadata(metadata_content, file)

    async def _find_file_and_metadata_name_by_id(
        self, backup_id: str
    ) -> tuple[FileVersion | None, str | None]:
        """Find the main backup file and determine its associated metadata file name by backup ID."""
        all_files_in_prefix = await self._get_all_files_in_prefix()

        # Iterate through metadata files to find the one matching backup_id
        for file_name, file_version in all_files_in_prefix.items():
            if not file_name.endswith(METADATA_FILE_SUFFIX):
                continue

            try:
                downloaded_meta = await self._hass.async_add_executor_job(
                    file_version.download
                )
                metadata_content = json.loads(downloaded_meta.text_content)
            except (B2Error, json.JSONDecodeError) as err:
                _LOGGER.warning(
                    "Failed to parse metadata file %s during ID search: %s",
                    file_name,
                    err,
                )
                continue

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and metadata_content.get("backup_id") == backup_id
            ):
                # Found the metadata file for the given backup_id
                found_metadata_file_name = file_name
                # Find the corresponding backup file (e.g., .tar)
                # It should start with the backup_id and not be a metadata file
                found_backup_file = next(
                    (
                        archive_file_version
                        for archive_file_name, archive_file_version in all_files_in_prefix.items()
                        if archive_file_name.startswith(self._prefix + backup_id)
                        and not archive_file_name.endswith(METADATA_FILE_SUFFIX)
                    ),
                    None,
                )

                if found_backup_file:
                    _LOGGER.debug(
                        "Found backup file %s and metadata file %s from id %s",
                        found_backup_file.file_name,
                        found_metadata_file_name,
                        backup_id,
                    )
                    return found_backup_file, found_metadata_file_name

                _LOGGER.warning(
                    "Found metadata file %s for backup ID %s, but no corresponding backup file",
                    file_name,
                    backup_id,
                )

        _LOGGER.debug("Backup %s not found", backup_id)
        return None, None

    def _backup_from_b2_metadata(
        self, metadata_content: dict[str, Any], backup_file: FileVersion
    ) -> AgentBackup:
        """Construct an AgentBackup from parsed metadata content and the associated backup file."""
        metadata = metadata_content["backup_metadata"]  # This is now the dict directly
        metadata["size"] = backup_file.size
        # metadata["name"] = backup_file.file_name
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
            metadata_content = json.loads(downloaded_meta.text_content)

            if (
                metadata_content.get("metadata_version") == METADATA_VERSION
                and "backup_id" in metadata_content
                and "backup_metadata" in metadata_content
            ):
                backup_id = file_name[len(self._prefix) : -len(METADATA_FILE_SUFFIX)]
                found_backup_archive_file = None

                for (
                    archive_file_name,
                    archive_file_version,
                ) in all_files_in_prefix.items():
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
