"""Backup platform for the S3 integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import json
import logging
from time import time
from typing import Any, cast

from botocore.exceptions import BotoCoreError

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

from . import S3ConfigEntry
from .const import CONF_BUCKET, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
CACHE_TTL = 300


def handle_boto_errors[T](
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Handle BotoCoreError exceptions by converting them to BackupAgentError."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        """Catch BotoCoreError and raise BackupAgentError."""
        try:
            return await func(*args, **kwargs)
        except BotoCoreError as err:
            error_msg = f"Failed during {func.__name__}"
            raise BackupAgentError(error_msg) from err

    return wrapper


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
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


def suggested_filenames(backup: AgentBackup) -> tuple[str, str]:
    """Return the suggested filenames for the backup and metadata files."""
    base_name = suggested_filename(backup).rsplit(".", 1)[0]
    return f"{base_name}.tar", f"{base_name}.metadata.json"


class S3BackupAgent(BackupAgent):
    """Backup agent for the S3 integration."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: S3ConfigEntry) -> None:
        """Initialize the S3 agent."""
        super().__init__()
        self._client = entry.runtime_data
        self._bucket = cast(str, entry.data[CONF_BUCKET])
        self.name = entry.title
        self.unique_id = cast(str, entry.unique_id)
        self._backup_cache = cast(dict[str, AgentBackup], {})
        self._cache_expiration = time()

    @handle_boto_errors
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
        tar_filename, _ = suggested_filenames(backup)

        response = await self._client.get_object(Bucket=self._bucket, Key=tar_filename)
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
        tar_filename, metadata_filename = suggested_filenames(backup)

        # Upload the backup file
        upload_id = None
        try:
            multipart_upload = await self._client.create_multipart_upload(
                Bucket=self._bucket,
                Key=tar_filename,
            )

            upload_id = multipart_upload["UploadId"]
            parts: list = []
            part_number = 1

            stream = await open_stream()
            async for chunk in stream:
                part = await self._client.upload_part(
                    Bucket=self._bucket,
                    Key=tar_filename,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk,
                )
                parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
                part_number += 1

            await self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=tar_filename,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

            # Upload the metadata file
            metadata_content = json.dumps(backup.as_dict())
            await self._client.put_object(
                Bucket=self._bucket,
                Key=metadata_filename,
                Body=metadata_content,
            )

            # Reset cache after successful upload
            self._cache_expiration = time()

        except BotoCoreError as err:
            if upload_id:
                try:
                    await self._client.abort_multipart_upload(
                        Bucket=self._bucket,
                        Key=tar_filename,
                        UploadId=upload_id,
                    )
                except BotoCoreError:
                    _LOGGER.exception("Failed to abort multipart upload")
            raise BackupAgentError("Failed to upload backup") from err

    @handle_boto_errors
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        backup = await self._find_backup_by_id(backup_id)
        tar_filename, metadata_filename = suggested_filenames(backup)

        # Delete both the backup file and its metadata file
        await self._client.delete_object(Bucket=self._bucket, Key=tar_filename)
        await self._client.delete_object(Bucket=self._bucket, Key=metadata_filename)

        # Reset cache after successful deletion
        self._cache_expiration = time()

    @handle_boto_errors
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups = await self._list_backups()
        return list(backups.values())

    @handle_boto_errors
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup."""
        return await self._find_backup_by_id(backup_id)

    async def _find_backup_by_id(self, backup_id: str) -> AgentBackup:
        """Find a backup by its backup ID."""
        backups = await self._list_backups()
        if backup := backups.get(backup_id):
            return backup

        raise BackupNotFound(f"Backup {backup_id} not found")

    async def _list_backups(self) -> dict[str, AgentBackup]:
        """List backups, using a cache if possible."""
        if time() <= self._cache_expiration:
            return self._backup_cache

        backups = {}
        response = await self._client.list_objects_v2(Bucket=self._bucket)

        # Filter for metadata files only
        metadata_files = [
            obj
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".metadata.json")
        ]

        for metadata_file in metadata_files:
            try:
                # Download and parse metadata file
                metadata_response = await self._client.get_object(
                    Bucket=self._bucket, Key=metadata_file["Key"]
                )
                metadata_content = await metadata_response["Body"].read()
                backup = AgentBackup.from_dict(json.loads(metadata_content))
                backups[backup.backup_id] = backup
            except (BotoCoreError, json.JSONDecodeError) as err:
                _LOGGER.warning(
                    "Failed to process metadata file %s: %s",
                    metadata_file["Key"],
                    err,
                )
                continue

        self._backup_cache = backups
        self._cache_expiration = time() + CACHE_TTL

        return self._backup_cache
