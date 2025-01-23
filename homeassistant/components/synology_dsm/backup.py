"""Support for Synology DSM backup agents."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import logging
from typing import Any

from synology_dsm.api.file_station import SynoFileStation
from synology_dsm.exceptions import SynologyDSMAPIErrorException

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import ChunkAsyncStreamIterator
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import (
    CONF_BACKUP_PATH,
    CONF_BACKUP_SHARE,
    DOMAIN,
    SYNOLOGY_DATA_BACKUP_AGENT_LISTENERS,
)
from .models import SynologyDSMData

LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    if not (
        entries := hass.config_entries.async_loaded_entries(DOMAIN)
    ) or not hass.data.get(DOMAIN):
        LOGGER.debug("No proper config entry found")
        return []
    agents: list[BackupAgent] = []
    for entry in entries:
        syno_data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
        if syno_data.api.file_station and entry.options.get(CONF_BACKUP_PATH):
            agents.append(SynologyDSMBackupAgent(hass, entry))
    return agents


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
    hass.data.setdefault(SYNOLOGY_DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[SYNOLOGY_DATA_BACKUP_AGENT_LISTENERS].remove(listener)

    return remove_listener


class SynologyDSMBackupAgent(BackupAgent):
    """Synology DSM backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Synology DSM backup agent."""
        super().__init__()
        LOGGER.debug("Initializing Synology DSM backup agent for %s", entry.unique_id)
        self.name = entry.title
        self.path = (
            f"{entry.options[CONF_BACKUP_SHARE]}/{entry.options[CONF_BACKUP_PATH]}"
        )
        syno_data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
        self.api = syno_data.api

    @property
    def _file_station(self) -> SynoFileStation:
        if not self.api.file_station:
            raise BackupAgentError("Synology FileStation API not available")
        return self.api.file_station

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        try:
            resp = await self._file_station.download_file(
                path=self.path,
                filename=f"{backup_id}.tar",
            )
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to download backup") from err

        if isinstance(resp, bool) or resp is None:
            raise BackupAgentError("Failed to download backup")

        return ChunkAsyncStreamIterator(resp)

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

        # upload backup.tar file first
        try:
            await self._file_station.upload_file(
                path=self.path,
                filename=f"{backup.backup_id}.tar",
                source=await open_stream(),
                create_parents=True,
            )
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to upload backup") from err

        # upload backup_meta.json file when backup.tar was successful uploaded
        try:
            await self._file_station.upload_file(
                path=self.path,
                filename=f"{backup.backup_id}_meta.json",
                source=json_dumps(backup.as_dict()).encode(),
            )
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to upload backup") from err

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        if not await self.async_get_backup(backup_id):
            return

        try:
            await self._file_station.delete_file(
                path=self.path, filename=f"{backup_id}.tar"
            )
            await self._file_station.delete_file(
                path=self.path, filename=f"{backup_id}_meta.json"
            )
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to delete the backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""

        async def _download_meta_data(filename: str) -> JsonObjectType:
            try:
                resp = await self._file_station.download_file(
                    path=self.path, filename=filename
                )
            except SynologyDSMAPIErrorException as err:
                raise BackupAgentError("Failed to download meta data") from err

            if isinstance(resp, bool) or resp is None:
                raise BackupAgentError("Failed to download meta data")

            try:
                return json_loads_object(await resp.read())
            except Exception as err:
                raise BackupAgentError("Failed to read meta data") from err

        try:
            files = await self._file_station.get_files(path=self.path)
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to list backups") from err

        if files is None:
            raise BackupAgentError("Failed to list backups")

        return [
            AgentBackup.from_dict(await _download_meta_data(file.name))
            for file in files
            if file.name.endswith("_meta.json")
        ]

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
