"""Support for Synology DSM backup agents."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import StreamReader
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
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
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
    syno_datas: dict[str, SynologyDSMData] = hass.data[DOMAIN]
    return [
        SynologyDSMBackupAgent(hass, entry, entry.unique_id)
        for entry in entries
        if entry.unique_id is not None
        and (syno_data := syno_datas.get(entry.unique_id))
        and syno_data.api.file_station
        and entry.options.get(CONF_BACKUP_PATH)
    ]


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


class SynologyDSMBackupAgent(BackupAgent):
    """Synology DSM backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, unique_id: str) -> None:
        """Initialize the Synology DSM backup agent."""
        super().__init__()
        LOGGER.debug("Initializing Synology DSM backup agent for %s", entry.unique_id)
        self.name = entry.title
        self.unique_id = unique_id
        self.path = (
            f"{entry.options[CONF_BACKUP_SHARE]}/{entry.options[CONF_BACKUP_PATH]}"
        )
        syno_data: SynologyDSMData = hass.data[DOMAIN][entry.unique_id]
        self.api = syno_data.api

    @property
    def _file_station(self) -> SynoFileStation:
        if TYPE_CHECKING:
            # we ensure that file_station exist already in async_get_backup_agents
            assert self.api.file_station
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
        try:
            resp = await self._file_station.download_file(
                path=self.path,
                filename=f"{backup_id}.tar",
            )
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to download backup") from err

        if TYPE_CHECKING:
            assert isinstance(resp, StreamReader)

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
        for filename in (f"{backup_id}.tar", f"{backup_id}_meta.json"):
            try:
                await self._file_station.delete_file(path=self.path, filename=filename)
            except SynologyDSMAPIErrorException as err:
                err_args: dict = err.args[0]
                if int(err_args.get("code", 0)) != 900 or (
                    (err_details := err_args.get("details")) is not None
                    and isinstance(err_details, list)
                    and isinstance(err_details[0], dict)
                    and int(err_details[0].get("code", 0))
                    != 408  # No such file or directory
                ):
                    LOGGER.error("Failed to delete backup: %s", err)
                    raise BackupAgentError("Failed to delete backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return list((await self._async_list_backups(**kwargs)).values())

    async def _async_list_backups(self, **kwargs: Any) -> dict[str, AgentBackup]:
        """List backups."""

        async def _download_meta_data(filename: str) -> JsonObjectType:
            try:
                resp = await self._file_station.download_file(
                    path=self.path, filename=filename
                )
            except SynologyDSMAPIErrorException as err:
                raise BackupAgentError("Failed to download meta data") from err

            if TYPE_CHECKING:
                assert isinstance(resp, StreamReader)

            try:
                return json_loads_object(await resp.read())
            except Exception as err:
                raise BackupAgentError("Failed to read meta data") from err

        try:
            files = await self._file_station.get_files(path=self.path)
        except SynologyDSMAPIErrorException as err:
            raise BackupAgentError("Failed to list backups") from err

        if TYPE_CHECKING:
            assert files

        backups: dict[str, AgentBackup] = {}
        for file in files:
            if file.name.endswith("_meta.json"):
                try:
                    meta_data = await _download_meta_data(file.name)
                except BackupAgentError as err:
                    LOGGER.error("Failed to download meta data: %s", err)
                    continue
                agent_backup = AgentBackup.from_dict(meta_data)
                backups[agent_backup.backup_id] = agent_backup
        return backups

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        backups = await self._async_list_backups()
        return backups.get(backup_id)
