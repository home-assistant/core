"""Backup platform for the Google Drive integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientTimeout, MultipartWriter, StreamReader

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import (
    ChunkAsyncStreamIterator,
    async_get_clientsession,
)

from . import DATA_BACKUP_AGENT_LISTENERS, GoogleDriveConfigEntry
from .api import create_headers
from .const import DOMAIN, DRIVE_API_FILES, DRIVE_API_UPLOAD_FILES

_LOGGER = logging.getLogger(__name__)
_UPLOAD_TIMEOUT = 12 * 3600


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return [GoogleDriveBackupAgent(hass, entry) for entry in entries]


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

    return remove_listener


class GoogleDriveBackupAgent(BackupAgent):
    """Google Drive backup agent."""

    domain = DOMAIN

    def __init__(
        self, hass: HomeAssistant, config_entry: GoogleDriveConfigEntry
    ) -> None:
        """Initialize the cloud backup sync agent."""
        super().__init__()
        self.name = config_entry.title
        self._hass = hass
        self._folder_id = config_entry.unique_id
        self._auth = config_entry.runtime_data

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
        headers = await self._async_headers()
        backup_metadata = {
            "name": f"{backup.name} {backup.date}.tar",
            "description": json.dumps(backup.as_dict()),
            "parents": [self._folder_id],
            "properties": {
                "ha": "backup",
                "backup_id": backup.backup_id,
            },
        }
        try:
            _LOGGER.debug(
                "Uploading backup: %s with Google Drive metadata: %s",
                backup,
                backup_metadata,
            )
            await self._async_upload(headers, backup_metadata, open_stream)
            _LOGGER.debug(
                "Uploaded backup: %s to: '%s'",
                backup.backup_id,
                backup_metadata["name"],
            )
        except (ClientError, TimeoutError) as err:
            _LOGGER.error("Upload backup error: %s", err)
            raise BackupAgentError("Failed to upload backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        headers = await self._async_headers()
        query = " and ".join(
            [
                f"'{self._folder_id}' in parents",
                "trashed=false",
            ]
        )
        try:
            res = await self._async_query(
                headers, query, "files(description,properties)"
            )
        except ClientError as err:
            raise BackupAgentError("Failed to list backups") from err
        backups = []
        for file in res["files"]:
            if "properties" not in file or "backup_id" not in file["properties"]:
                continue
            backup = AgentBackup.from_dict(json.loads(file["description"]))
            backups.append(backup)
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

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        _LOGGER.debug("Downloading backup_id: %s", backup_id)
        headers = await self._async_headers()
        file_id = await self._async_get_backup_file_id(headers, backup_id)
        if file_id:
            try:
                stream = await self._async_download(headers, file_id)
            except ClientError as err:
                _LOGGER.error("Download error: %s", err)
                raise BackupAgentError("Failed to download backup") from err
            return ChunkAsyncStreamIterator(stream)
        _LOGGER.error("Download backup_id: %s not found", backup_id)
        raise BackupAgentError("Backup not found")

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        _LOGGER.debug("Deleting backup_id: %s", backup_id)
        headers = await self._async_headers()
        file_id = await self._async_get_backup_file_id(headers, backup_id)
        if file_id:
            try:
                resp = await async_get_clientsession(self._hass).delete(
                    f"{DRIVE_API_FILES}/{file_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                _LOGGER.debug("Deleted backup_id: %s", backup_id)
            except ClientError as err:
                _LOGGER.error("Delete backup error: %s", err)
                raise BackupAgentError("Failed to delete backup") from err

    async def _async_headers(self) -> dict[str, str]:
        try:
            access_token = await self._auth.check_and_refresh_token()
        except HomeAssistantError as err:
            raise BackupAgentError("Failed to refresh token") from err
        return create_headers(access_token)

    async def _async_upload(
        self,
        headers: dict[str, str],
        file_metadata: dict[str, Any],
        open_stream: Callable[
            [], Coroutine[Any, Any, AsyncIterator[bytes]] | Awaitable[bytes]
        ],
    ) -> None:
        with MultipartWriter() as mpwriter:
            mpwriter.append_json(file_metadata)
            mpwriter.append(await open_stream())
            headers.update(
                {"Content-Type": f"multipart/related; boundary={mpwriter.boundary}"}
            )
            resp = await async_get_clientsession(self._hass).post(
                DRIVE_API_UPLOAD_FILES,
                params={"fields": ""},
                data=mpwriter,
                headers=headers,
                timeout=ClientTimeout(total=_UPLOAD_TIMEOUT),
            )
            resp.raise_for_status()

    async def _async_download(
        self, headers: dict[str, str], file_id: str
    ) -> StreamReader:
        resp = await async_get_clientsession(self._hass).get(
            f"{DRIVE_API_FILES}/{file_id}",
            params={"alt": "media"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.content

    async def _async_get_backup_file_id(
        self,
        headers: dict[str, str],
        backup_id: str,
    ) -> str | None:
        query = " and ".join(
            [
                f"'{self._folder_id}' in parents",
                f"properties has {{ key='backup_id' and value='{backup_id}' }}",
            ]
        )
        try:
            res = await self._async_query(headers, query, "files(id)")
        except ClientError as err:
            _LOGGER.error("_async_get_backup_file_id error: %s", err)
            raise BackupAgentError("Failed to get backup") from err
        for file in res["files"]:
            return str(file["id"])
        return None

    async def _async_query(
        self,
        headers: dict[str, str],
        query: str,
        fields: str,
    ) -> dict[str, Any]:
        _LOGGER.debug("_async_query: query: %s fields: %s", query, fields)
        resp = await async_get_clientsession(self._hass).get(
            DRIVE_API_FILES,
            params={
                "q": query,
                "fields": fields,
            },
            headers=headers,
        )
        resp.raise_for_status()
        res: dict[str, Any] = await resp.json()
        _LOGGER.debug("_async_query result: %s", res)
        return res
