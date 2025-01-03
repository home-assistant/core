"""Backup platform for the Google Drive integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
import json
from typing import Any, Self

from aiogoogle import Aiogoogle
from aiogoogle.auth import UserCreds
from aiogoogle.excs import AiogoogleError
from aiohttp import ClientError, StreamReader

from homeassistant.components.backup import AgentBackup, BackupAgent, BackupAgentError
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DATA_BACKUP_AGENT_LISTENERS, GoogleDriveConfigEntry
from .api import AsyncConfigEntryAuth, convert_to_user_creds
from .const import DOMAIN

# Google Drive only supports string key value pairs as properties.
# We convert any other fields to JSON strings.
_AGENT_BACKUP_SIMPLE_FIELDS = [
    "backup_id",
    "date",
    "database_included",
    "homeassistant_included",
    "homeassistant_version",
    "name",
    "protected",
    "size",
]


def _convert_agent_backup_to_properties(backup: AgentBackup) -> dict[str, str]:
    return {
        k: v if k in _AGENT_BACKUP_SIMPLE_FIELDS else json.dumps(v)
        for k, v in backup.as_dict().items()
    }


def _convert_properties_to_agent_backup(d: dict[str, str]) -> AgentBackup:
    return AgentBackup.from_dict(
        {
            k: v if k in _AGENT_BACKUP_SIMPLE_FIELDS else json.loads(v)
            for k, v in d.items()
        }
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


class ChunkAsyncStreamIterator:
    """Async iterator for chunked streams.

    Based on aiohttp.streams.ChunkTupleAsyncStreamIterator, but yields
    bytes instead of tuple[bytes, bool].
    """

    __slots__ = ("_stream",)

    def __init__(self, stream: StreamReader) -> None:
        """Initialize."""
        self._stream = stream

    def __aiter__(self) -> Self:
        """Iterate."""
        return self

    async def __anext__(self) -> bytes:
        """Yield next chunk."""
        rv = await self._stream.readchunk()
        if rv == (b"", False):
            raise StopAsyncIteration
        return rv[0]


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
        self._auth: AsyncConfigEntryAuth = config_entry.runtime_data

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
        properties = _convert_agent_backup_to_properties(backup)
        async with Aiogoogle(user_creds=await self._creds()) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            req = drive_v3.files.create(
                pipe_from=await open_stream(),
                fields="",
                json={
                    "name": f"{backup.name} {backup.date}.tar",
                    "parents": [self._folder_id],
                    "properties": properties,
                },
            )
            try:
                await aiogoogle.as_user(req, timeout=12 * 3600)
            except (AiogoogleError, TimeoutError) as err:
                raise BackupAgentError("Failed to upload backup") from err

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        async with Aiogoogle(user_creds=await self._creds()) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            query = f"'{self._folder_id}' in parents and trashed=false"
            try:
                res = await aiogoogle.as_user(
                    drive_v3.files.list(q=query, fields="files(properties)"),
                    full_res=True,
                )
            except AiogoogleError as err:
                raise BackupAgentError("Failed to list backups") from err
        backups = []
        async for page in res:
            for file in page["files"]:
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
        async with Aiogoogle(user_creds=await self._creds()) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            try:
                res = await aiogoogle.as_user(
                    drive_v3.files.list(
                        q=self._query(backup_id),
                        fields="files(properties)",
                    )
                )
            except AiogoogleError as err:
                raise BackupAgentError("Failed to get backup") from err
            for file in res["files"]:
                return _convert_properties_to_agent_backup(file["properties"])
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
        user_creds = await self._creds()
        async with Aiogoogle(user_creds=user_creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            try:
                res = await aiogoogle.as_user(
                    drive_v3.files.list(
                        q=self._query(backup_id),
                        fields="files(id)",
                    )
                )
            except AiogoogleError as err:
                raise BackupAgentError("Failed to get backup") from err
            for file in res["files"]:
                # Intentionally not passing pipe_to and not wrapping this via aiogoogle.as_user
                # to avoid downloading the whole file in memory
                req = drive_v3.files.get(fileId=file["id"], alt="media")
                req = aiogoogle.oauth2.authorize(req, user_creds)
                try:
                    resp = await async_get_clientsession(self._hass).get(
                        req.url, headers=req.headers
                    )
                    resp.raise_for_status()
                except ClientError as err:
                    raise BackupAgentError("Failed to download backup") from err
                return ChunkAsyncStreamIterator(resp.content)
        raise BackupAgentError("Backup not found")

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        async with Aiogoogle(user_creds=await self._creds()) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            try:
                res = await aiogoogle.as_user(
                    drive_v3.files.list(
                        q=self._query(backup_id),
                        fields="files(id)",
                    )
                )
            except AiogoogleError as err:
                raise BackupAgentError("Failed to get backup") from err
            for file in res["files"]:
                try:
                    await aiogoogle.as_user(drive_v3.files.delete(fileId=file["id"]))
                except AiogoogleError as err:
                    raise BackupAgentError("Failed to delete backup") from err

    def _query(self, backup_id: str) -> str:
        return " and ".join(
            [
                f"'{self._folder_id}' in parents",
                f"properties has {{ key='backup_id' and value='{backup_id}' }}",
            ]
        )

    async def _creds(self) -> UserCreds:
        try:
            await self._auth.check_and_refresh_token()
        except HomeAssistantError as err:
            raise BackupAgentError("Failed to authorize") from err
        return convert_to_user_creds(self._auth.oauth_session.token)
