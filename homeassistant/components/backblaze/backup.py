"""Backup platform for the Backblaze integration."""

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
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
METADATA_VERSION = "1"


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
        self.async_create_task = entry.async_create_task
        self._bucket = entry.runtime_data.bucket
        self._prefix = entry.runtime_data.prefix

        self.name = entry.title
        self.unique_id = entry.entry_id

    @handle_b2_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup."""

        file = await self._find_file_by_id(backup_id)
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

        file_info = {
            "metadata_version": METADATA_VERSION,
            "backup_id": backup.backup_id,
            "backup_metadata": json.dumps(backup.as_dict()),
        }

        filename = self._prefix + suggested_filename(backup)

        _LOGGER.debug("Uploading %s", filename)

        stream: AsyncIterator[bytes] = await open_stream()

        # Create a pipe (file descriptors) to bridge async writes and sync reads
        r_fd, w_fd = os.pipe()

        async def writer() -> None:
            """Write async stream to the pipe."""
            with os.fdopen(w_fd, "wb") as w:
                async for chunk in stream:
                    w.write(chunk)
                w.close()

        # Schedule the writer coroutine
        writer_task = self.async_create_task(self._hass, writer())

        def upload() -> None:
            with os.fdopen(r_fd, "rb") as r:
                self._bucket.upload_unbound_stream(
                    r,
                    filename,
                    file_info=file_info,
                )

        await self._hass.async_add_executor_job(upload)
        await writer_task

    @handle_b2_errors
    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup."""
        file = await self._find_file_by_id(backup_id)
        if file is None:
            raise BackupNotFound(f"Backup {backup_id} not found")
        _LOGGER.debug("Deleting %s", backup_id)
        await self._hass.async_add_executor_job(file.delete)

    @handle_b2_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List all backups."""
        backups: list[AgentBackup] = []

        def get_files() -> None:
            for [file, _] in self._bucket.ls(self._prefix):
                if (
                    file.file_info is not None
                    and file.file_info.get("metadata_version") == METADATA_VERSION
                ):
                    backups.append(
                        AgentBackup.from_dict(
                            json.loads(file.file_info["backup_metadata"])
                        )
                    )

        await self._hass.async_add_executor_job(get_files)
        _LOGGER.debug("Found %d backups", len(backups))
        return backups

    @handle_b2_errors
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Get a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _find_file_by_id(self, backup_id: str) -> FileVersion | None:
        """Find a file by its ID."""

        def find_file() -> FileVersion | None:
            for [file, _] in self._bucket.ls(self._prefix):
                if (
                    file.file_info is not None
                    and file.file_info.get("metadata_version") == METADATA_VERSION
                    and file.file_info.get("backup_id") == backup_id
                ):
                    _LOGGER.debug("Found file %s from id %s", file.file_name, backup_id)
                    return file
            _LOGGER.debug("File %s not found", backup_id)
            return None

        return await self._hass.async_add_executor_job(find_file)

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its ID."""
        file = await self._find_file_by_id(backup_id)
        if file is None:
            raise BackupNotFound(f"Backup {backup_id} not found")
        metadata = file.file_info.get("backup_metadata")
        if metadata is None:
            raise BackupNotFound(f"Backup {backup_id} not found")
        return AgentBackup.from_dict(json.loads(metadata))
