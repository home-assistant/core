"""Support for OneDrive backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import html
import json
import logging
from typing import Any, Concatenate

from aiohttp import ClientTimeout
from onedrive_personal_sdk.clients.large_file_upload import LargeFileUploadClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    HashMismatchError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import File, Folder, ItemUpdate
from onedrive_personal_sdk.models.upload import FileInfo

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import OneDriveConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
UPLOAD_CHUNK_SIZE = 16 * 320 * 1024  # 5.2MB
TIMEOUT = ClientTimeout(connect=10, total=43200)  # 12 hours


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[OneDriveConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    return [OneDriveBackupAgent(hass, entry) for entry in entries]


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
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[OneDriveBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors with a specific translation key."""

    @wraps(func)
    async def wrapper(
        self: OneDriveBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except AuthenticationError as err:
            self._entry.async_start_reauth(self._hass)
            raise BackupAgentError("Authentication error") from err
        except OneDriveException as err:
            _LOGGER.error(
                "Error during backup in %s:, message %s",
                func.__name__,
                err,
            )
            _LOGGER.debug("Full error: %s", err, exc_info=True)
            raise BackupAgentError("Backup operation failed") from err
        except TimeoutError as err:
            _LOGGER.error(
                "Error during backup in %s: Timeout",
                func.__name__,
            )
            raise BackupAgentError("Backup operation timed out") from err

    return wrapper


class OneDriveBackupAgent(BackupAgent):
    """OneDrive backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
        """Initialize the OneDrive backup agent."""
        super().__init__()
        self._hass = hass
        self._entry = entry
        self._client = entry.runtime_data.client
        self._token_provider = entry.runtime_data.token_provider
        self._folder_id = entry.runtime_data.backup_folder_id
        self.name = entry.title
        assert entry.unique_id
        self.unique_id = entry.unique_id

    @handle_backup_errors
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup file."""
        item = await self._find_item_by_backup_id(backup_id)
        if item is None:
            raise BackupAgentError("Backup not found")

        stream = await self._client.download_drive_item(item.id, timeout=TIMEOUT)
        return stream.iter_chunked(1024)

    @handle_backup_errors
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""

        filename = suggested_filename(backup)

        file = FileInfo(
            filename,
            backup.size,
            self._folder_id,
            await open_stream(),
        )
        try:
            await LargeFileUploadClient.upload(
                self._token_provider, file, session=async_get_clientsession(self._hass)
            )
        except HashMismatchError as err:
            raise BackupAgentError(
                "Hash validation failed, backup file might be corrupt"
            ) from err

        # store metadata in description
        backup_dict = backup.as_dict()
        backup_dict["metadata_version"] = 1  # version of the backup metadata
        description = json.dumps(backup_dict)
        _LOGGER.debug("Creating metadata: %s", description)

        await self._client.update_drive_item(
            path_or_id=f"{self._folder_id}:/{filename}:",
            data=ItemUpdate(description=description),
        )

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""
        item = await self._find_item_by_backup_id(backup_id)
        if item is None:
            return
        await self._client.delete_drive_item(item.id)

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return [
            self._backup_from_description(item.description)
            for item in await self._client.list_drive_items(self._folder_id)
            if item.description and "homeassistant_version" in item.description
        ]

    @handle_backup_errors
    async def async_get_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AgentBackup | None:
        """Return a backup."""
        item = await self._find_item_by_backup_id(backup_id)
        return (
            self._backup_from_description(item.description)
            if item and item.description
            else None
        )

    def _backup_from_description(self, description: str) -> AgentBackup:
        """Create a backup object from a description."""
        description = html.unescape(
            description
        )  # OneDrive encodes the description on save automatically
        return AgentBackup.from_dict(json.loads(description))

    async def _find_item_by_backup_id(self, backup_id: str) -> File | Folder | None:
        """Find an item by backup ID."""
        return next(
            (
                item
                for item in await self._client.list_drive_items(self._folder_id)
                if item.description and backup_id in item.description
            ),
            None,
        )
