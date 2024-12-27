"""Support for Azure Storage backup."""

from collections.abc import AsyncIterator, Callable, Coroutine
import json
import logging
from typing import Any

from azure.core.exceptions import HttpResponseError

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback

from . import AzureStorageConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


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

    return remove_listener


class AzureStorageBackupAgent(BackupAgent):
    """Azure storage backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: AzureStorageConfigEntry) -> None:
        """Initialize the Azure storage backup agent."""
        super().__init__()
        self._client = entry.runtime_data
        self.name = entry.title

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        try:
            download_stream = await self._client.download_blob(f"{backup_id}.tar")
            return download_stream.chunks()
        except HttpResponseError as err:
            _LOGGER.debug(
                "Failed to download backup %s: %s", backup_id, err, exc_info=True
            )
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="backup_download_error",
                translation_placeholders={"backup_id": backup_id},
            ) from err

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""

        backup_dict = backup.as_dict()

        if backup.folders:
            backup_dict["folders"] = json.dumps(backup.folders)

        if backup.addons:
            backup_dict["addons"] = json.dumps(backup.addons)

        if backup.extra_metadata:
            backup_dict["extra_metadata"] = json.dumps(backup.extra_metadata)

        # ensure dict is [str, str]
        backup_dict = {str(k): str(v) for k, v in backup_dict.items()}

        try:
            await self._client.upload_blob(
                name=f"{backup.backup_id}.tar",
                metadata=backup_dict,
                data=await open_stream(),
                length=backup.size,
            )
        except HttpResponseError as err:
            _LOGGER.debug(
                "Failed to upload backup %s: %s", backup.backup_id, err, exc_info=True
            )
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="backup_upload_error",
                translation_placeholders={"backup_id": backup.backup_id},
            ) from err

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        try:
            await self._client.delete_blob(f"{backup_id}.tar")
        except HttpResponseError as err:
            _LOGGER.debug(
                "Failed to delete backup %s: %s", backup_id, err, exc_info=True
            )
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="backup_delete_error",
                translation_placeholders={"backup_id": backup_id},
            ) from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups: list[AgentBackup] = []

        try:
            async for blob in self._client.list_blobs(include="metadata"):
                metadata = blob.metadata

                if "homeassistant_version" in metadata:
                    metadata["folders"] = json.loads(metadata.get("folders", "[]"))
                    metadata["addons"] = json.loads(metadata.get("addons", "[]"))
                    metadata["extra_metadata"] = json.loads(
                        metadata.get("extra_metadata", "{}")
                    )
                    backups.append(AgentBackup.from_dict(metadata))
        except HttpResponseError as err:
            _LOGGER.debug("Failed to list backups: %s", err, exc_info=True)
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="backup_list_error",
            ) from err
        return backups

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        backups = await self.async_list_backups()

        for backup in backups:
            if backup.backup_id == backup_id:
                return backup

        return None
