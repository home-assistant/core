"""Backup platform for the Backblaze integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from b2sdk.v2.exception import B2Error

from homeassistant.components.backup import (
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    Folder,
)
from homeassistant.core import HomeAssistant, callback

from . import BackblazeConfigEntry
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN, SEPARATOR
from .util import BufferedAsyncIteratorToSyncStream


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    entries: list[BackblazeConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    return [BackblazeBackupAgent(hass, entry) for entry in entries]


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

    return remove_listener


class BackblazeBackupAgent(BackupAgent):
    """Backblaze backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: BackblazeConfigEntry) -> None:
        """Initialize the Backblaze backup sync agent."""
        super().__init__()
        self._bucket = entry.runtime_data.bucket
        self._api = entry.runtime_data.api
        self._hass = hass
        self.name = entry.title

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file from Backblaze."""
        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        try:
            downloaded_file = await self._hass.async_add_executor_job(
                self._bucket.download_file_by_name, f"{backup_id}.tar"
            )
        except B2Error as err:
            raise BackupAgentError(
                f"Failed to download backup {backup_id}: {err}"
            ) from err

        if not downloaded_file.response.ok:
            raise BackupAgentError(
                f"Failed to download backup {backup_id}: HTTP {downloaded_file.response.status_code}"
            )

        # Use an executor to avoid blocking the event loop
        for chunk in await self._hass.async_add_executor_job(
            downloaded_file.response.iter_content, 1024
        ):
            yield chunk

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""

        # Prepare file info metadata to store with the backup in Backblaze
        # Backblaze can only store a mapping of strings to strings, so we need
        # to serialize the metadata into a string format.
        file_info = {
            "backup_id": backup.backup_id,
            "database_included": str(backup.database_included).lower(),
            "date": backup.date,
            "extra_metadata": "###META###".join(
                f"{key}{SEPARATOR}{val}" for key, val in backup.extra_metadata.items()
            ),
            "homeassistant_included": str(backup.homeassistant_included).lower(),
            "homeassistant_version": backup.homeassistant_version,
            "name": backup.name,
            "protected": str(backup.protected).lower(),
            "size": str(backup.size),
        }
        if backup.addons:
            file_info["addons"] = "###ADDON###".join(
                f"{addon.slug}{SEPARATOR}{addon.version}{SEPARATOR}{addon.name}"
                for addon in backup.addons
            )
        if backup.folders:
            file_info["folders"] = ",".join(folder.value for folder in backup.folders)

        iterator = await open_stream()
        stream = BufferedAsyncIteratorToSyncStream(
            iterator,
            buffer_size=8 * 1024 * 1024,  # Buffer up to 8MB
        )
        try:
            await self._hass.async_add_executor_job(
                self._bucket.upload_unbound_stream,
                stream,
                f"{backup.backup_id}.tar",
                "application/octet-stream",
                file_info,
            )
        except B2Error as err:
            raise BackupAgentError(
                f"Failed to upload backup {backup.backup_id}: {err}"
            ) from err

    def _delete_backup(
        self,
        backup_id: str,
    ) -> None:
        """Delete file from Backblaze."""
        try:
            file_info = self._bucket.get_file_info_by_name(f"{backup_id}.tar")
            self._api.delete_file_version(
                file_info.id_,
                file_info.file_name,
            )
        except B2Error as err:
            raise BackupAgentError(
                f"Failed to delete backup {backup_id}: {err}"
            ) from err

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file from Backblaze."""
        if not await self.async_get_backup(backup_id):
            return

        await self._hass.async_add_executor_job(self._delete_backup, backup_id)

    def _list_backups(self) -> list[AgentBackup]:
        """List backups stored on Backblaze."""
        backups = []
        try:
            for file_version, _ in self._bucket.ls(latest_only=True):
                file_info = file_version.file_info

                if "homeassistant_version" not in file_info:
                    continue

                addons: list[AddonInfo] = []
                if addons_string := file_version.file_info.get("addons"):
                    for addon in addons_string.split("###ADDON###"):
                        slug, version, name = addon.split(SEPARATOR)
                        addons.append(AddonInfo(slug=slug, version=version, name=name))

                extra_metadata = {}
                if extra_metadata_string := file_info.get("extra_metadata"):
                    for meta in extra_metadata_string.split("###META###"):
                        key, val = meta.split(SEPARATOR)
                        extra_metadata[key] = val

                folders: list[Folder] = []
                if folder_string := file_version.file_info.get("folders"):
                    folders = [
                        Folder(folder) for folder in folder_string.split(SEPARATOR)
                    ]

                backups.append(
                    AgentBackup(
                        backup_id=file_info["backup_id"],
                        name=file_info["name"],
                        date=file_info["date"],
                        size=int(file_info["size"]),
                        homeassistant_version=file_info["homeassistant_version"],
                        protected=file_info["protected"] == "true",
                        addons=addons,
                        folders=folders,
                        database_included=file_info["database_included"] == "true",
                        homeassistant_included=file_info["database_included"] == "true",
                        extra_metadata=extra_metadata,
                    )
                )
        except B2Error as err:
            raise BackupAgentError(f"Failed to list backups: {err}") from err

        return backups

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups stored on Backblaze."""
        return await self._hass.async_add_executor_job(self._list_backups)

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
