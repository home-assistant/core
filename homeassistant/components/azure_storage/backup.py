"""Support for Azure Storage backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from copy import deepcopy
from functools import wraps
import json
import logging
from typing import Any, Concatenate

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from slugify import slugify

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback

from . import AzureStorageConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[AzureStorageConfigEntry] = hass.config_entries.async_entries(DOMAIN)
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
    """Handle backup errors with a specific translation key."""

    @wraps(func)
    async def wrapper(
        self: AzureStorageBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except HttpResponseError as err:
            _LOGGER.error(
                "Error during backup in %s: Status %s, message %s",
                func.__name__,
                err.status_code,
                err.message,
            )
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError("Error during backup operation") from err

    return wrapper


class AzureStorageBackupAgent(BackupAgent):
    """Azure storage backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: AzureStorageConfigEntry) -> None:
        """Initialize the Azure storage backup agent."""
        super().__init__()
        self._client = entry.runtime_data
        self.name = slugify(entry.title)
        self.unique_id = entry.entry_id

    @handle_backup_errors
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        download_stream = await self._client.download_blob(f"{backup_id}.tar")
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
            **backup.as_dict(),
            "metadata_version": 1,
            "folders": json.dumps(backup.folders) if backup.folders else "",
            "addons": json.dumps(backup.addons) if backup.addons else "",
            "extra_metadata": (
                json.dumps(backup.extra_metadata) if backup.extra_metadata else ""
            ),
        }

        # ensure dict is [str, str]
        metadata = {str(k): str(v) for k, v in metadata.items()}

        await self._client.upload_blob(
            name=f"{backup.backup_id}.tar",
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
        await self._client.delete_blob(f"{backup_id}.tar")

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []
        async for blob in self._client.list_blobs(include="metadata"):
            metadata = blob.metadata

            if "homeassistant_version" in metadata:
                backups.append(self._parse_blob_metadata(metadata))

        return backups

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        blob_client = self._client.get_blob_client(f"{backup_id}.tar")
        try:
            blob_properties = await blob_client.get_blob_properties()
        except ResourceNotFoundError:
            return None

        return self._parse_blob_metadata(blob_properties.metadata)

    def _parse_blob_metadata(self, metadata: dict[str, Any]) -> AgentBackup:
        """Parse backup metadata."""
        agent_backup = deepcopy(metadata)
        agent_backup["folders"] = (
            json.loads(metadata["folders"]) if metadata.get("folders") else []
        )
        agent_backup["addons"] = (
            json.loads(metadata["addons"]) if metadata.get("addons") else []
        )
        agent_backup["extra_metadata"] = (
            json.loads(metadata["extra_metadata"])
            if metadata.get("extra_metadata")
            else {}
        )
        agent_backup["protected"] = metadata.get("protected") == "True"
        agent_backup["database_included"] = metadata.get("database_included") == "True"
        agent_backup["homeassistant_included"] = (
            metadata.get("homeassistant_included") == "True"
        )
        agent_backup["size"] = int(metadata.get("size", 0))
        return AgentBackup.from_dict(agent_backup)
