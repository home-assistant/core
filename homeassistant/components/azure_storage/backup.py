"""Support for Azure Storage backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import json
import logging
from typing import Any, Concatenate

from azure.core.exceptions import HttpResponseError
from azure.storage.blob import BlobProperties

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

from . import AzureStorageConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
METADATA_VERSION = "1"


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[AzureStorageConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    return [AzureStorageBackupAgent(hass, entry) for entry in entries]


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
            hass.data.pop(DATA_BACKUP_AGENT_LISTENERS)

    return remove_listener


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[AzureStorageBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[AzureStorageBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors."""

    @wraps(func)
    async def wrapper(
        self: AzureStorageBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except HttpResponseError as err:
            _LOGGER.debug(
                "Error during backup in %s: Status %s, message %s",
                func.__name__,
                err.status_code,
                err.message,
                exc_info=True,
            )
            raise BackupAgentError(
                f"Error during backup operation in {func.__name__}:"
                f" Status {err.status_code}, message: {err.message}"
            ) from err

    return wrapper


class AzureStorageBackupAgent(BackupAgent):
    """Azure storage backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: AzureStorageConfigEntry) -> None:
        """Initialize the Azure storage backup agent."""
        super().__init__()
        self._client = entry.runtime_data
        self.name = entry.title
        self.unique_id = entry.entry_id

    @handle_backup_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        blob = await self._find_blob_by_backup_id(backup_id)
        if blob is None:
            raise BackupNotFound(f"Backup {backup_id} not found")
        download_stream = await self._client.download_blob(blob.name)
        return download_stream.chunks()

    @handle_backup_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""

        metadata = {
            "metadata_version": METADATA_VERSION,
            "backup_id": backup.backup_id,
            "backup_metadata": json.dumps(backup.as_dict()),
        }

        await self._client.upload_blob(
            name=suggested_filename(backup),
            metadata=metadata,
            data=await open_stream(),
            length=backup.size,
        )

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        blob = await self._find_blob_by_backup_id(backup_id)
        if blob is None:
            raise BackupNotFound(f"Backup {backup_id} not found")
        await self._client.delete_blob(blob.name)

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        async for blob in self._client.list_blobs(include="metadata"):
            metadata = blob.metadata

            if metadata.get("metadata_version") == METADATA_VERSION:
                backups.append(
                    AgentBackup.from_dict(json.loads(metadata["backup_metadata"]))
                )

        return backups

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        blob = await self._find_blob_by_backup_id(backup_id)
        if blob is None:
            raise BackupNotFound(f"Backup {backup_id} not found")

        return AgentBackup.from_dict(json.loads(blob.metadata["backup_metadata"]))

    async def _find_blob_by_backup_id(self, backup_id: str) -> BlobProperties | None:
        """Find a blob by backup id."""
        async for blob in self._client.list_blobs(include="metadata"):
            if (
                blob.metadata is not None
                and backup_id == blob.metadata.get("backup_id", "")
                and blob.metadata.get("metadata_version") == METADATA_VERSION
            ):
                return blob
        return None
