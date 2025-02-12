"""Support for WebDAV backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from aiohttp import ClientTimeout
from aiowebdav2 import Property, PropertyRequest
from aiowebdav2.exceptions import UnauthorizedError, WebDavError
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

METADATA_VERSION = "1"
BACKUP_TIMEOUT = ClientTimeout(connect=10, total=43200)


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


def handle_backup_errors[_R, **P](
    func: Callable[Concatenate[WebDavBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[WebDavBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Handle backup errors."""

    @wraps(func)
    async def wrapper(self: WebDavBackupAgent, *args: P.args, **kwargs: P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except UnauthorizedError as err:
            raise BackupAgentError("Authentication error") from err
        except WebDavError as err:
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

    @handle_backup_errors
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
        if backup is None:
            raise BackupAgentError("Backup not found")

        return await self._client.download_iter(
            f"{self._backup_path}/{suggested_filename(backup)}",
            timeout=BACKUP_TIMEOUT,
        )

    @handle_backup_errors
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
            timeout=BACKUP_TIMEOUT,
        )

        _LOGGER.debug(
            "Uploaded backup to %s",
            f"{self._backup_path}/{filename}",
        )

        metadata_filename = filename.rsplit(".", 1)[0] + ".metadata.json"
        await self._client.upload_iter(
            json_dumps(backup.as_dict()),
            f"{self._backup_path}/{metadata_filename}",
            timeout=BACKUP_TIMEOUT,
        )

        await self._client.set_property_batch(
            f"{self._backup_path}/{metadata_filename}",
            [
                Property(
                    namespace="homeassistant",
                    name="backup_id",
                    value=backup.backup_id,
                ),
                Property(
                    namespace="homeassistant",
                    name="metadata_version",
                    value=METADATA_VERSION,
                ),
            ],
        )

        _LOGGER.debug(
            "Uploaded metadata file for %s",
            f"{self._backup_path}/{filename}",
        )

    @handle_backup_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        backup = await self._find_backup_by_id(backup_id)
        if backup is None:
            return

        filename = suggested_filename(backup)
        await self._client.clean(f"{self._backup_path}/{filename}")
        metadata_filename = filename.rsplit(".", 1)[0] + ".metadata.json"
        await self._client.clean(f"{self._backup_path}/{metadata_filename}")

        _LOGGER.debug(
            "Deleted backup at %s",
            f"{self._backup_path}/{suggested_filename(backup)}",
        )

    @handle_backup_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        metadata_files = await self._list_metadata_files()
        return [
            await self._download_metadata(metadata_file)
            for metadata_file in metadata_files
        ]

    @handle_backup_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _list_metadata_files(self) -> list[str]:
        """List metadata files."""
        files = await self._client.list_with_infos(self._backup_path)
        return [
            file["path"]
            for file in files
            if file["path"].endswith(".json")
            and await self._is_current_metadata_version(file["path"])
        ]

    async def _is_current_metadata_version(self, path: str) -> bool:
        """Check if is current metadata version."""
        metadata_version = await self._client.get_property(
            path,
            PropertyRequest(
                namespace="homeassistant",
                name="metadata_version",
            ),
        )
        return metadata_version.value == METADATA_VERSION if metadata_version else False

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup | None:
        """Find a backup by its backup ID on remote."""
        metadata_files = await self._list_metadata_files()
        for metadata_file in metadata_files:
            remote_backup_id = await self._client.get_property(
                metadata_file,
                PropertyRequest(
                    namespace="homeassistant",
                    name="backup_id",
                ),
            )
            if remote_backup_id and remote_backup_id.value == backup_id:
                return await self._download_metadata(metadata_file)

        return None

    async def _download_metadata(self, path: str) -> AgentBackup:
        """Download metadata file."""
        iterator = await self._client.download_iter(path)
        metadata = await anext(iterator)
        return AgentBackup.from_dict(json_loads_object(metadata))
