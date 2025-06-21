"""Support for SFTPClient backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
from json import loads as json_loads
import logging
from typing import Any, Concatenate

from asyncssh import SFTPError
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

from . import SFTPClientConfigEntry
from .const import (
    CONF_BACKUP_PATH,
    DATA_BACKUP_AGENT_LISTENERS,
    DEFAULT_BACKUP_PATH,
    DOMAIN,
)
from .helpers import CannotConnect, json_to_stream

_LOGGER = logging.getLogger(__name__)


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[SFTPClientConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    return [SFTPClientConfigEntryBackupAgent(hass, entry) for entry in entries]


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
    func: Callable[
        Concatenate[SFTPClientConfigEntryBackupAgent, P], Coroutine[Any, Any, _R]
    ],
) -> Callable[
    Concatenate[SFTPClientConfigEntryBackupAgent, P], Coroutine[Any, Any, _R]
]:
    """Handle backup errors."""

    @wraps(func)
    async def wrapper(
        self: SFTPClientConfigEntryBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except SFTPError as err:
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(f"Backup operation failed: {err}") from err

    return wrapper


# pyright: reportIncompatibleMethodOverride=none


class SFTPClientConfigEntryBackupAgent(BackupAgent):
    """Backup agent interface."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: SFTPClientConfigEntry) -> None:
        """Initialize the SFTPClient backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self.sftp = entry.runtime_data
        self.name = entry.title
        self.unique_id = entry.entry_id
        self._cache_metadata_files: dict[str, AgentBackup] = {}

    @cached_property
    def _backup_path(self) -> str:
        """Return the path to the backup."""
        return self._entry.data.get(CONF_BACKUP_PATH, DEFAULT_BACKUP_PATH)

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

        remote_path = f"{self._backup_path}/{suggested_filename(backup)}"

        try:
            await self.sftp.async_connect()
        except CannotConnect as err:
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(f"Failed to connect to SFTP server: {err}") from err

        if self.sftp.client is None:
            raise BackupAgentError("Failed to connect to SFTP server without a client")

        sftp_file = await self.sftp.client.open(remote_path, "rb")

        async def stream_chunks() -> AsyncIterator[bytes]:
            try:
                while True:
                    chunk: bytes = await sftp_file.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await sftp_file.close()
                await self.sftp.async_close()

        return stream_chunks()

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

        try:
            await self.sftp.async_connect()
        except CannotConnect as err:
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(f"Failed to connect to SFTP server: {err}") from err

        if self.sftp.client is None:
            raise BackupAgentError("Failed to connect to SFTP server without a client")

        source_stream = await open_stream()
        tar_path = f"{self._backup_path}/{filename_tar}"
        async with await self.sftp.client.open(tar_path, "wb") as sftp_file:
            async for chunk in source_stream:
                await sftp_file.write(chunk)

        metadata_content = json_dumps(backup.as_dict())
        source_stream = json_to_stream(metadata_content)
        meta_path = f"{self._backup_path}/{filename_meta}"
        async with await self.sftp.client.open(meta_path, "wb") as sftp_file:
            async for chunk in source_stream:
                await sftp_file.write(chunk)

        await self.sftp.async_close()

    @handle_backup_errors
    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        backup = await self._find_backup_by_id(backup_id)

        (filename_tar, filename_meta) = suggested_filenames(backup)

        try:
            await self.sftp.async_connect()
        except CannotConnect as err:
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(f"Failed to connect to SFTP server: {err}") from err

        if self.sftp.client is None:
            raise BackupAgentError("Failed to connect to SFTP server without a client")

        await self.sftp.client.remove(f"{self._backup_path}/{filename_tar}")
        await self.sftp.client.remove(f"{self._backup_path}/{filename_meta}")
        await self.sftp.async_close()

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return list((await self._async_list_backups()).values())

    async def _async_list_backups(self, **kwargs: Any) -> dict[str, AgentBackup]:
        """List metadata files with a cache."""

        try:
            await self.sftp.async_connect()
        except CannotConnect as err:
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError(f"Failed to connect to SFTP server: {err}") from err

        async def _download_metadata(path: str) -> AgentBackup:
            """Download metadata file."""
            if self.sftp.client is None:
                raise BackupAgentError(
                    "Failed to connect to SFTP server without a client"
                )

            chunks: list[bytes] = []
            async with await self.sftp.client.open(path, "rb") as sftp_file:
                while True:
                    chunk: bytes = await sftp_file.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)

            metadata_bytes = b"".join(chunks)
            metadata = json_loads(metadata_bytes.decode("utf-8"))
            return AgentBackup.from_dict(metadata)

        async def _list_metadata_files() -> dict[str, AgentBackup]:
            """List metadata files."""
            if self.sftp.client is None:
                raise BackupAgentError(
                    "Failed to connect to SFTP server without a client"
                )

            files = await self.sftp.client.listdir(self._backup_path)
            metadata_files = {}
            for file_name in files:
                if file_name.endswith(".metadata.json"):
                    metadata_content = await _download_metadata(
                        f"{self._backup_path}/{file_name}"
                    )
                    if metadata_content:
                        metadata_files[metadata_content.backup_id] = metadata_content
            return metadata_files

        metadata_files = await _list_metadata_files()
        await self.sftp.async_close()
        return metadata_files

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its backup ID on remote."""
        metadata_files = await self._async_list_backups()
        if metadata_file := metadata_files.get(backup_id):
            return metadata_file

        raise BackupNotFound(f"Backup {backup_id} not found")
