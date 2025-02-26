"""Backup platform for the S3 integration."""

from collections.abc import AsyncGenerator, AsyncIterator, Callable, Coroutine
import json
import logging
from typing import Any

from homeassistant.components.backup import AgentBackup, BackupAgent, suggested_filename
from homeassistant.core import HomeAssistant, callback

from . import S3ConfigEntry
from .const import CONF_BUCKET, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
METADATA_VERSION = "1"


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[S3ConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return [S3BackupAgent(hass, entry) for entry in entries]


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


def _get_key(backup: AgentBackup) -> str:
    """Return the key for a backup."""
    return f"{backup.backup_id}_{suggested_filename(backup)}"


def _serialize(metadata: dict[str, Any]) -> dict[str, str]:
    """Serialize metadata."""
    return {k: json.dumps(v) for k, v in metadata.items()}


def _deserialize(metadata: dict[str, str]) -> dict[str, Any]:
    """Deserialize metadata."""
    return {k: json.loads(v) for k, v in metadata.items()}


class S3BackupAgent(BackupAgent):
    """Backup agent for the S3 integration."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: S3ConfigEntry) -> None:
        """Initialize the S3 agent."""
        super().__init__()
        self._client = entry.runtime_data
        self._bucket = entry.data[CONF_BUCKET]
        self.name = entry.title
        self.unique_id = entry.entry_id

    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        _LOGGER.debug("Downloading backup with ID %s", backup_id)
        _, obj = await self._get_backup(backup_id)
        response = await self._client.get_object(Bucket=self._bucket, Key=obj["Key"])
        return response["Body"].iter_chunks()

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
        _LOGGER.debug("Uploading backup with ID %s", backup.backup_id)

        key = _get_key(backup)
        metadata = {
            "metadata_version": METADATA_VERSION,
            "backup_metadata": backup.as_dict(),
        }

        multipart_upload = await self._client.create_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            Metadata=_serialize(metadata),
        )

        upload_id = multipart_upload["UploadId"]
        parts = []
        part_number = 1

        stream = await open_stream()
        async for chunk in stream:
            part = await self._client.upload_part(
                Bucket=self._bucket,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=chunk,
            )
            parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
            part_number += 1

        await self._client.complete_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        _LOGGER.debug("Deleting backup with ID %s", backup_id)
        _, obj = await self._get_backup(backup_id)
        await self._client.delete_object(Bucket=self._bucket, Key=obj["Key"])

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        _LOGGER.debug("Listing backups")
        return [backup async for backup, _ in self._list_backups()]

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        try:
            backup, _ = await self._get_backup(backup_id)
        except ValueError:
            return None
        else:
            return backup

    async def _get_backup(self, backup_id: str) -> tuple[AgentBackup, dict]:
        """Get a backup and its object."""
        _LOGGER.debug("Getting backup with ID %s", backup_id)
        try:
            backup, obj = await anext(self._list_backups(backup_id))
        except StopAsyncIteration:
            raise ValueError(f"Backup with ID {backup_id} not found") from None
        else:
            _LOGGER.debug("Found matching object %s", obj["Key"])
            return backup, obj

    async def _list_backups(
        self, backup_id: str | None = None
    ) -> AsyncGenerator[tuple[AgentBackup, dict]]:
        """List backups and its objects, optionally filtering by backup_id."""
        async for obj in self._list_objects(backup_id):
            obj_head = await self._client.head_object(
                Bucket=self._bucket, Key=obj["Key"]
            )
            obj_meta = _deserialize(obj_head.get("Metadata", {}))
            if obj_meta.get("metadata_version") == METADATA_VERSION:
                backup = AgentBackup.from_dict(obj_meta["backup_metadata"])
                yield backup, obj

    async def _list_objects(self, backup_id: str | None = None) -> AsyncGenerator[dict]:
        """List objects, optionally filtering by backup_id prefix."""
        response = await self._client.list_objects_v2(Bucket=self._bucket)
        for obj in response.get("Contents", []):
            if backup_id is None or obj["Key"].startswith(f"{backup_id}_"):
                yield obj
