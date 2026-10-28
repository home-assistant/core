"""Backup platform for the Seafile integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import suppress
from functools import wraps
from typing import Any, Concatenate, override

from aioseafile import (
    DirentType,
    Seafile,
    SeafileError,
    SeafileNotFoundError,
    SeafileTimeoutError,
)
from yarl import URL

from homeassistant.components.backup import (
    DOMAIN as BACKUP_DOMAIN,
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    OnProgressCallback,
    suggested_filename,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_bytes
from homeassistant.util.async_ import gather_with_limited_concurrency
from homeassistant.util.json import json_loads_object

from .const import (
    CONF_BACKUP,
    CONF_BACKUP_PATH,
    CONF_LIBRARY_ID,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_LIBRARY,
)
from .coordinator import SeafileConfigEntry

# Uploads are split in requests of this size, so they pass proxies that limit
# the request body size, such as Cloudflare (100 MB).
UPLOAD_CHUNK_SIZE = 50 * 1024 * 1024
METADATA_SUFFIX = "_meta.json"


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the names of the backup file and its metadata file."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}{METADATA_SUFFIX}"


async def async_get_backup_agents(hass: HomeAssistant) -> list[BackupAgent]:
    """Return a backup agent for every library that stores backups."""
    entries: list[SeafileConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return [
        SeafileBackupAgent(entry, subentry)
        for entry in entries
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LIBRARY)
        if subentry.data[CONF_BACKUP]
    ]


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
    func: Callable[Concatenate[SeafileBackupAgent, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[SeafileBackupAgent, P], Coroutine[Any, Any, _R]]:
    """Convert Seafile errors into backup agent errors."""

    @wraps(func)
    async def wrapper(
        self: SeafileBackupAgent, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except SeafileTimeoutError as err:
            raise BackupAgentError(
                translation_domain=BACKUP_DOMAIN,
                translation_key="agent_operation_timed_out",
            ) from err
        except SeafileError as err:
            LOGGER.debug("Error during backup in %s: %s", func.__name__, err)
            raise BackupAgentError(
                translation_domain=BACKUP_DOMAIN,
                translation_key="agent_operation_failed",
            ) from err

    return wrapper


class SeafileBackupAgent(BackupAgent):
    """Store backups in a folder of a Seafile library."""

    domain = DOMAIN

    def __init__(self, entry: SeafileConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__()
        self._client: Seafile = entry.runtime_data.client
        self._library_id: str = subentry.data[CONF_LIBRARY_ID]
        self._path: str = subentry.data[CONF_BACKUP_PATH]
        self.name = f"{entry.title} - {subentry.title}"
        self.unique_id = subentry.subentry_id

    def _file_path(self, name: str) -> str:
        return f"{self._path.rstrip('/')}/{name}"

    async def _async_list_backups(self) -> dict[str, tuple[AgentBackup, str]]:
        """Return the backups with the base name of their files."""
        try:
            listing = await self._client.get_directory(
                self._library_id, self._path, entry_type=DirentType.FILE
            )
        except SeafileNotFoundError:
            # The folder is created with the first backup.
            return {}
        base_names = [
            entry.name.removesuffix(METADATA_SUFFIX)
            for entry in listing.entries
            if entry.name.endswith(METADATA_SUFFIX)
        ]
        results = await gather_with_limited_concurrency(
            4,
            *(self._async_read_metadata(base_name) for base_name in base_names),
        )
        return {
            backup.backup_id: (backup, base_name)
            for backup, base_name in zip(results, base_names, strict=True)
            if backup is not None
        }

    async def _async_read_metadata(self, base_name: str) -> AgentBackup | None:
        """Read a metadata file, or return None if it is gone or unreadable."""
        try:
            content = b"".join(
                [
                    chunk
                    async for chunk in self._client.download_file(
                        self._library_id,
                        self._file_path(f"{base_name}{METADATA_SUFFIX}"),
                    )
                ]
            )
        except SeafileNotFoundError:
            # Deleted while the folder was being listed.
            return None
        try:
            return AgentBackup.from_dict(json_loads_object(content))
        except (ValueError, KeyError, TypeError) as err:
            LOGGER.warning("Skipping invalid backup metadata %s: %s", base_name, err)
            return None

    async def _async_find_backup(self, backup_id: str) -> tuple[AgentBackup, str]:
        """Return a backup and the base name of its files."""
        if (found := (await self._async_list_backups()).get(backup_id)) is None:
            raise BackupNotFound(
                translation_domain=BACKUP_DOMAIN,
                translation_key="backup_not_found",
                translation_placeholders={"backup_id": backup_id},
            )
        return found

    @handle_backup_errors
    @override
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        on_progress: OnProgressCallback,
        **kwargs: Any,
    ) -> None:
        """Upload a backup and its metadata."""
        tar_name, metadata_name = suggested_filenames(backup)
        if self._path != "/":
            await self._client.create_directory(self._library_id, self._path)
        await self._client.upload_file(
            self._library_id,
            self._path,
            tar_name,
            await open_stream(),
            size=backup.size,
            replace=True,
            chunk_size=UPLOAD_CHUNK_SIZE,
            on_progress=lambda uploaded: on_progress(bytes_uploaded=uploaded),
        )
        # The metadata is written last, so a backup is only listed when complete.
        try:
            await self._client.upload_file(
                self._library_id,
                self._path,
                metadata_name,
                json_bytes(backup.as_dict()),
                replace=True,
            )
        except SeafileError:
            # Don't leave a backup file behind that is never listed.
            with suppress(SeafileError):
                await self._client.delete_items(
                    self._library_id, self._path, [tar_name]
                )
            raise

    @handle_backup_errors
    @override
    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup."""
        _, base_name = await self._async_find_backup(backup_id)
        link = await self._client.get_download_link(
            self._library_id, self._file_path(f"{base_name}.tar")
        )
        return self._async_stream(link)

    async def _async_stream(self, link: URL) -> AsyncIterator[bytes]:
        """Stream a download, converting errors while it is read."""
        try:
            async for chunk in self._client.download(link):
                yield chunk
        except SeafileTimeoutError as err:
            raise BackupAgentError(
                translation_domain=BACKUP_DOMAIN,
                translation_key="agent_operation_timed_out",
            ) from err
        except SeafileError as err:
            raise BackupAgentError(
                translation_domain=BACKUP_DOMAIN,
                translation_key="agent_operation_failed",
            ) from err

    @handle_backup_errors
    @override
    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup and its metadata."""
        _, base_name = await self._async_find_backup(backup_id)
        await self._client.delete_items(
            self._library_id,
            self._path,
            [f"{base_name}.tar", f"{base_name}{METADATA_SUFFIX}"],
        )

    @handle_backup_errors
    @override
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List the backups in the folder."""
        return [backup for backup, _ in (await self._async_list_backups()).values()]

    @handle_backup_errors
    @override
    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Return a backup."""
        backup, _ = await self._async_find_backup(backup_id)
        return backup
