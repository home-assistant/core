"""Backup platform for the Google Drive integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, override

from google_drive_api.exceptions import GoogleDriveApiError

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    OnProgressCallback,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import DATA_BACKUP_AGENT_LISTENERS
from .const import DOMAIN
from .coordinator import GoogleDriveConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_get_backup_agents(
    hass: HomeAssistant,
    **kwargs: Any,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return [GoogleDriveBackupAgent(entry) for entry in entries]


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


class GoogleDriveBackupAgent(BackupAgent):
    """Google Drive backup agent."""

    domain = DOMAIN

    def __init__(self, config_entry: GoogleDriveConfigEntry) -> None:
        """Initialize the cloud backup sync agent."""
        super().__init__()
        assert config_entry.unique_id
        self.name = config_entry.title
        self.unique_id = slugify(config_entry.unique_id)
        self._client = config_entry.runtime_data.client

    @override
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        on_progress: OnProgressCallback,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param open_stream: A function returning an async iterator that yields bytes.
        :param backup: Metadata about the backup that should be uploaded.
        """

        bytes_uploaded = 0

        @wraps(open_stream)
        async def wrapped_open_stream() -> AsyncIterator[bytes]:
            stream = await open_stream()

            async def _progress_stream() -> AsyncIterator[bytes]:
                nonlocal bytes_uploaded
                position = 0
                async for chunk in stream:
                    yield chunk
                    position += len(chunk)
                    # A retried upload reopens the stream from the beginning and
                    # skips whatever the server already received, so only report
                    # progress once it passes what was previously uploaded.
                    if position > bytes_uploaded:
                        bytes_uploaded = position
                        on_progress(bytes_uploaded=bytes_uploaded)

            return _progress_stream()

        try:
            await self._client.async_upload_backup(wrapped_open_stream, backup)
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            _LOGGER.error("Failed to upload backup: %s", err)
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="upload_failed",
            ) from err

    @override
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        try:
            return await self._client.async_list_backups()
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            _LOGGER.error("Failed to list backups: %s", err)
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="list_failed",
            ) from err

    @override
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        backups = await self.async_list_backups()
        for backup in backups:
            if backup.backup_id == backup_id:
                return backup
        raise BackupNotFound(
            translation_domain=BACKUP_DOMAIN,
            translation_key="backup_not_found",
            translation_placeholders={"backup_id": backup_id},
        )

    @override
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
        try:
            file_id = await self._client.async_get_backup_file_id(backup_id)
            if file_id:
                _LOGGER.debug("Downloading file_id: %s", file_id)
                return await self._client.async_download(file_id)
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            _LOGGER.error("Failed to download backup: %s", err)
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="download_failed",
            ) from err
        raise BackupNotFound(
            translation_domain=BACKUP_DOMAIN,
            translation_key="backup_not_found",
            translation_placeholders={"backup_id": backup_id},
        )

    @override
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        _LOGGER.debug("Deleting backup_id: %s", backup_id)
        try:
            file_id = await self._client.async_get_backup_file_id(backup_id)
            if file_id:
                _LOGGER.debug("Deleting file_id: %s", file_id)
                await self._client.async_delete(file_id)
                _LOGGER.debug("Deleted backup_id: %s", backup_id)
                return
        except (GoogleDriveApiError, HomeAssistantError, TimeoutError) as err:
            _LOGGER.error("Failed to delete backup: %s", err)
            raise BackupAgentError(
                translation_domain=DOMAIN,
                translation_key="delete_failed",
            ) from err
        raise BackupNotFound(
            translation_domain=BACKUP_DOMAIN,
            translation_key="backup_not_found",
            translation_placeholders={"backup_id": backup_id},
        )
