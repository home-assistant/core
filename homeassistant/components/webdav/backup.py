"""Support for WebDAV backup."""

from collections.abc import AsyncIterator, Callable, Coroutine
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads_object

from . import WebDavConfigEntry
from .const import CONF_BACKUP_PATH, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[WebDavConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return [WebDavBackupAgent(hass, entry) for entry in entries]


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


class WebDavBackupAgent(BackupAgent):
    """Backup agent interface."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: WebDavConfigEntry) -> None:
        """Initialize the WebDAV backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._client = entry.runtime_data
        self.name = entry.title
        assert entry.unique_id
        self.unique_id = entry.unique_id

    @cached_property
    def _backup_path(self) -> str:
        """Return the path to the backup."""
        return self._entry.data.get(CONF_BACKUP_PATH, "")

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
        return await self._client.download_iter(
            f"{self._backup_path}/{suggested_filename(backup)}"
        )

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
        filename = suggested_filename(backup)
        await self._client.upload_iter(
            await open_stream(),
            f"{self._backup_path}/{filename}",
        )

        _LOGGER.debug(
            "Uploaded backup to %s",
            f"{self._backup_path}/{filename}",
        )

        await self._client.set_property_batch(
            f"{self._backup_path}/{filename}",
            [
                {
                    "namespace": "homeassistant",
                    "name": "backup_id",
                    "value": backup.backup_id,
                },
                {
                    "namespace": "homeassistant",
                    "name": "metadata",
                    "value": json_dumps(backup.as_dict()),
                },
            ],
        )

        _LOGGER.debug(
            "Set metadata for %s",
            f"{self._backup_path}/{filename}",
        )

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        backup = await self._find_backup_by_id(backup_id)

        await self._client.clean(f"{self._backup_path}/{suggested_filename(backup)}")
        _LOGGER.debug(
            "Deleted backup at %s",
            f"{self._backup_path}/{suggested_filename(backup)}",
        )

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        files = await self._client.list(self._backup_path, get_info=True)

        backups = []
        for file in files:
            if not file["isdir"] and file["path"].endswith(".tar"):
                prop = await self._client.get_property(
                    file["path"], {"namespace": "homeassistant", "name": "metadata"}
                )
                if prop is None:
                    _LOGGER.debug("Missing metadata for %s", file["path"])

                backups.append(AgentBackup.from_dict(json_loads_object(prop)))

        return backups

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its backup ID on remote."""
        files = await self._client.list(self._backup_path, get_info=True)

        for file in files:
            if not file["isdir"] and file["path"].endswith(".tar"):
                remote_backup_id = await self._client.get_property(
                    file["path"], {"namespace": "homeassistant", "name": "backup_id"}
                )
                if remote_backup_id == backup_id:
                    prop = await self._client.get_property(
                        file["path"], {"namespace": "homeassistant", "name": "metadata"}
                    )
                    if prop:
                        return AgentBackup.from_dict(json_loads_object(prop))
                    _LOGGER.debug("Missing metadata for %s", file["path"])

        raise BackupAgentError("Backup not found")
