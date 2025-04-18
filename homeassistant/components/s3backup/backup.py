"""Backup platform for the S3 integration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any, Self

from botocore.response import StreamingBody

from homeassistant.components.backup import (
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    Folder,
)
from homeassistant.core import HomeAssistant, callback

from . import S3ConfigEntry
from .const import CONF_BUCKET, DATA_BACKUP_AGENT_LISTENERS, DOMAIN, LOGGER, SEPARATOR
from .util import BufferedAsyncIteratorToSyncStream


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Register the backup agents."""
    entries: list[S3ConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    return [S3BackupAgent(hass, entry) for entry in entries]


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


class ChunkAsyncStreamIterator:
    """Async iterator for chunked streams.

    Based on aiohttp.streams.ChunkTupleAsyncStreamIterator, but yields
    bytes instead of tuple[bytes, bool].
    """

    __slots__ = ("_stream",)

    def __init__(self, stream: StreamingBody) -> None:
        """Initialize."""
        self._stream = stream

    def __aiter__(self) -> Self:
        """Iterate."""
        return self

    async def __anext__(self) -> bytes:
        """Yield next chunk."""
        try:
            rv = self._stream.next()
        except StopIteration:
            raise StopAsyncIteration from None

        if rv == b"":
            raise StopAsyncIteration
        return rv


class S3BackupAgent(BackupAgent):
    """S3 backup agent."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: S3ConfigEntry) -> None:
        """Initialize the S3BackupAgent backup sync agent."""
        super().__init__()
        self._entry = entry
        self._hass = hass
        self.name = entry.title
        self.domain = DOMAIN

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file from S3."""
        if not await self.async_get_backup(backup_id):
            raise BackupAgentError("Backup not found")

        try:

            def download():
                return self._entry.runtime_data.client.get_object(
                    Bucket=self._entry.runtime_data.bucket,
                    Key=f"{backup_id}.tar",
                )

            downloaded_file = await self._hass.async_add_executor_job(
                download,
            )
        except Exception as err:
            raise BackupAgentError(
                f"Failed to download backup {backup_id}: {err}"
            ) from err

        if downloaded_file["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise BackupAgentError(
                f"Failed to download backup {backup_id}: HTTP {downloaded_file.ResponseMetadata.HTTPStatusCode}"
            )

        LOGGER.debug("Downloading file: %s", downloaded_file)

        return ChunkAsyncStreamIterator(downloaded_file["Body"])

    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        # Prepare file info metadata to store with the backup in S3
        # S3 can only store a mapping of strings to strings, so we need
        # to serialize the metadata into a string format.
        file_info: dict[str, Any] = {
            "Metadata": {
                "backup_id": backup.backup_id,
                "database_included": str(backup.database_included).lower(),
                "date": backup.date,
                "extra_metadata": "###META###".join(
                    f"{key}{SEPARATOR}{val}"
                    for key, val in backup.extra_metadata.items()
                ),
                "homeassistant_included": str(backup.homeassistant_included).lower(),
                "homeassistant_version": backup.homeassistant_version,
                "name": backup.name,
                "protected": str(backup.protected).lower(),
                "size": str(backup.size),
            }
        }
        if backup.addons:
            file_info["addons"] = "###ADDON###".join(
                f"{addon.slug}{SEPARATOR}{addon.version}{SEPARATOR}{addon.name}"
                for addon in backup.addons
            )
        if backup.folders:
            file_info["folders"] = ",".join(folder.value for folder in backup.folders)

        # Upload the file with metadata
        file_path = f"{backup.backup_id}.tar"
        bucket_name = self._entry.data[CONF_BUCKET]

        iterator = await open_stream()
        stream = BufferedAsyncIteratorToSyncStream(
            iterator,
            buffer_size=8 * 1024 * 1024,  # Buffer up to 8MB
        )

        # use boto client to send the stream to s3
        try:
            await self._hass.async_add_executor_job(
                self._entry.runtime_data.client.upload_fileobj,
                stream,
                bucket_name,
                file_path,
                file_info,
            )

            LOGGER.debug(
                f"File '{file_path}' uploaded to '{bucket_name}/{file_path}' with metadata."
            )
        except Exception as err:
            raise BackupAgentError(
                f"Error to upload backup: {backup.backup_id}: {err}"
            ) from err

    def _delete_backup(
        self,
        backup_id: str,
    ) -> None:
        """Delete file from S3."""
        try:
            self._entry.runtime_data.client.delete_object(
                Bucket=self._entry.runtime_data.bucket, Key=f"{backup_id}.tar"
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.error("Can not delete backups from location: %s", err)
            raise BackupAgentError(f"Failed to delete backups: {err}") from err

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file from S3."""
        if not await self.async_get_backup(backup_id):
            return

        await self._hass.async_add_executor_job(self._delete_backup, backup_id)

    def _list_backups(self) -> list[AgentBackup]:
        """List backups stored on S3."""
        backups = []

        try:
            response = self._entry.runtime_data.client.list_objects_v2(
                Bucket=self._entry.runtime_data.bucket
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.error("Can not read backups from location: %s", err)
            raise BackupAgentError(f"Failed to list backups: {err}") from err

        # Check if the bucket contains any objects
        if "Contents" in response:
            for obj in response["Contents"]:
                key = obj["Key"]
                # Retrieve metadata for each object
                metadata = self._entry.runtime_data.client.head_object(
                    Bucket=self._entry.runtime_data.bucket, Key=key
                )

                file_info = metadata["Metadata"]

                if file_info.get("homeassistant_version") is None:
                    continue

                addons: list[AddonInfo] = []
                if addons_string := file_info.get("addons"):
                    for addon in addons_string.split("###ADDON###"):
                        slug, version, name = addon.split(SEPARATOR)
                        addons.append(AddonInfo(slug=slug, version=version, name=name))

                extra_metadata = {}
                if extra_metadata_string := file_info.get("extra_metadata"):
                    for meta in extra_metadata_string.split("###META###"):
                        key, val = meta.split(SEPARATOR)
                        extra_metadata[key] = val

                folders: list[Folder] = []
                if folder_string := file_info.get("folders"):
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

        else:
            LOGGER.debug("No objects found in the bucket")

        return backups

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups stored on S3."""
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
