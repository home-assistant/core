"""Backup platform for the Google Drive integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import json
from typing import Any

from aiohttp import ClientError, ClientTimeout, MultipartWriter

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

_UPLOAD_TIMEOUT = 12 * 3600


# Google Drive only supports string key value pairs as properties.
# Convert every field to JSON strings except backup_id so that we can query it.
def _convert_agent_backup_to_properties(backup: AgentBackup) -> dict[str, str]:
    return {
        k: v if k == "backup_id" else json.dumps(v) for k, v in backup.as_dict().items()
    }


def _convert_properties_to_agent_backup(d: dict[str, str]) -> AgentBackup:
    return AgentBackup.from_dict(
        {k: v if k == "backup_id" else json.loads(v) for k, v in d.items()}
    )


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    return [
        GoogleDriveBackupAgent(hass=hass, config_entry=config_entry)
        for config_entry in hass.config_entries.async_loaded_entries(DOMAIN)
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
        properties = _convert_agent_backup_to_properties(backup)
        with MultipartWriter() as mpwriter:
            mpwriter.append_json(
                {
                    "name": f"{backup.name} {backup.date}.tar",
                    "parents": [self._folder_id],
                    "properties": properties,
                }
            )
            mpwriter.append(await open_stream())
            headers.update(
                {"Content-Type": f"multipart/related; boundary={mpwriter.boundary}"}
            )
            try:
                resp = await async_get_clientsession(self._hass).post(
                    DRIVE_API_UPLOAD_FILES,
                    params={"fields": ""},
                    data=mpwriter,
                    headers=headers,
                    timeout=ClientTimeout(total=_UPLOAD_TIMEOUT),
                )
                resp.raise_for_status()
            except (ClientError, TimeoutError) as err:
                raise BackupAgentError("Failed to upload backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        headers = await self._async_headers()
        try:
            resp = await async_get_clientsession(self._hass).get(
                DRIVE_API_FILES,
                params={
                    "q": f"'{self._folder_id}' in parents and trashed=false",
                    "fields": "files(properties)",
                },
                headers=headers,
            )
            resp.raise_for_status()
            res = await resp.json()
        except ClientError as err:
            raise BackupAgentError("Failed to list backups") from err
        backups = []
        for file in res["files"]:
            if "properties" not in file or "backup_id" not in file["properties"]:
                continue
            backup = _convert_properties_to_agent_backup(file["properties"])
            backups.append(backup)
        return backups

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        headers = await self._async_headers()
        _, backup = await self._async_get_file_id_and_properties(backup_id, headers)
        return backup

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        headers = await self._async_headers()
        file_id, _ = await self._async_get_file_id_and_properties(backup_id, headers)
        if file_id is None:
            raise BackupAgentError("Backup not found")
        try:
            resp = await async_get_clientsession(self._hass).get(
                f"{DRIVE_API_FILES}/{file_id}",
                params={"alt": "media"},
                headers=headers,
            )
            resp.raise_for_status()
        except ClientError as err:
            raise BackupAgentError("Failed to download backup") from err
        return ChunkAsyncStreamIterator(resp.content)

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        headers = await self._async_headers()
        file_id, _ = await self._async_get_file_id_and_properties(backup_id, headers)
        if file_id is None:
            return
        try:
            resp = await async_get_clientsession(self._hass).delete(
                f"{DRIVE_API_FILES}/{file_id}",
                headers=headers,
            )
            resp.raise_for_status()
        except ClientError as err:
            raise BackupAgentError("Failed to delete backup") from err

    async def _async_headers(self) -> dict[str, str]:
        try:
            access_token = await self._auth.check_and_refresh_token()
        except HomeAssistantError as err:
            raise BackupAgentError("Failed to refresh token") from err
        return create_headers(access_token)

    async def _async_get_file_id_and_properties(
        self, backup_id: str, headers: dict[str, str]
    ) -> tuple[str | None, AgentBackup | None]:
        query = " and ".join(
            [
                f"'{self._folder_id}' in parents",
                f"properties has {{ key='backup_id' and value='{backup_id}' }}",
            ]
        )
        try:
            resp = await async_get_clientsession(self._hass).get(
                DRIVE_API_FILES,
                params={
                    "q": query,
                    "fields": "files(id,properties)",
                },
                headers=headers,
            )
            resp.raise_for_status()
            res = await resp.json()
        except ClientError as err:
            raise BackupAgentError("Failed to get backup") from err
        for file in res["files"]:
            return file["id"], _convert_properties_to_agent_backup(file["properties"])
        return None, None
