"""Backup platform for the IDrive e2 integration."""

from collections.abc import AsyncIterator, Callable, Coroutine
import functools
import json
import logging
from time import time
from typing import Any

from botocore.exceptions import BotoCoreError

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupAgentError,
    BackupNotFound,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

from . import IDriveE2ConfigEntry
from .const import CONF_BUCKET, DATA_BACKUP_AGENT_LISTENERS, DOMAIN

_LOGGER = logging.getLogger(__name__)
CACHE_TTL = 300

# S3 part size requirements: 5 MiB to 5 GiB per part
# https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html
# We set the threshold to 20 MiB to avoid too many parts.
# Note that each part is allocated in the memory.
MULTIPART_MIN_PART_SIZE_BYTES = 20 * 2**20


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
    entries: list[IDriveE2ConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    return [IDriveE2BackupAgent(hass, entry) for entry in entries]


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


class IDriveE2BackupAgent(BackupAgent):
    """Backup agent for the IDrive e2 integration."""

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: IDriveE2ConfigEntry) -> None:
        """Initialize the IDrive e2 agent."""
        super().__init__()
        self._hass = hass
        self._client = entry.runtime_data
        self._bucket: str = entry.data[CONF_BUCKET]
        self.name = entry.title
        self.unique_id = entry.entry_id
        self._backup_cache: dict[str, AgentBackup] = {}
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

        response = await self._hass.async_add_executor_job(
            functools.partial(
                self._client.get_object, Bucket=self._bucket, Key=tar_filename
            )
        )

        async def stream_chunks() -> AsyncIterator[bytes]:
            for chunk in response["Body"].iter_chunks():
                yield chunk

        return stream_chunks()

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

        try:
            if backup.size < MULTIPART_MIN_PART_SIZE_BYTES:
                await self._upload_simple(tar_filename, open_stream)
            else:
                await self._upload_multipart(tar_filename, open_stream)

            # Upload the metadata file
            metadata_content = json.dumps(backup.as_dict())
            await self._hass.async_add_executor_job(
                functools.partial(
                    self._client.put_object,
                    Bucket=self._bucket,
                    Key=metadata_filename,
                    Body=metadata_content,
                )
            )
        except BotoCoreError as err:
            raise BackupAgentError("Failed to upload backup") from err
        else:
            # Reset cache after successful upload
            self._cache_expiration = time()

    async def _upload_simple(
        self,
        tar_filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
    ) -> None:
        """Upload a small file using simple upload.

        :param tar_filename: The target filename for the backup.
        :param open_stream: A function returning an async iterator that yields bytes.
        """
        _LOGGER.debug("Starting simple upload for %s", tar_filename)
        stream = await open_stream()
        file_data = bytearray()
        async for chunk in stream:
            file_data.extend(chunk)

        await self._hass.async_add_executor_job(
            functools.partial(
                self._client.put_object,
                Bucket=self._bucket,
                Key=tar_filename,
                Body=bytes(file_data),
            )
        )

    async def _upload_multipart(
        self,
        tar_filename: str,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
    ):
        """Upload a large file using multipart upload.

        :param tar_filename: The target filename for the backup.
        :param open_stream: A function returning an async iterator that yields bytes.
        """
        _LOGGER.debug("Starting multipart upload for %s", tar_filename)
        multipart_upload = await self._hass.async_add_executor_job(
            functools.partial(
                self._client.create_multipart_upload,
                Bucket=self._bucket,
                Key=tar_filename,
            )
        )
        upload_id = multipart_upload["UploadId"]
        try:
            parts = []
            part_number = 1
            buffer_size = 0  # bytes
            buffer: list[bytes] = []

            stream = await open_stream()
            async for chunk in stream:
                buffer_size += len(chunk)
                buffer.append(chunk)

                # If buffer size meets minimum part size, upload it as a part
                if buffer_size >= MULTIPART_MIN_PART_SIZE_BYTES:
                    _LOGGER.debug(
                        "Uploading part number %d, size %d", part_number, buffer_size
                    )
                    part = await self._hass.async_add_executor_job(
                        functools.partial(
                            self._client.upload_part,
                            Bucket=self._bucket,
                            Key=tar_filename,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=b"".join(buffer),
                        )
                    )
                    parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
                    part_number += 1
                    buffer_size = 0
                    buffer = []

            # Upload the final buffer as the last part (no minimum size requirement)
            if buffer:
                _LOGGER.debug(
                    "Uploading final part number %d, size %d", part_number, buffer_size
                )
                part = await self._hass.async_add_executor_job(
                    functools.partial(
                        self._client.upload_part,
                        Bucket=self._bucket,
                        Key=tar_filename,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=b"".join(buffer),
                    )
                )
                parts.append({"PartNumber": part_number, "ETag": part["ETag"]})

            await self._hass.async_add_executor_job(
                functools.partial(
                    self._client.complete_multipart_upload,
                    Bucket=self._bucket,
                    Key=tar_filename,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
            )

        except BotoCoreError:
            try:
                await self._hass.async_add_executor_job(
                    functools.partial(
                        self._client.abort_multipart_upload,
                        Bucket=self._bucket,
                        Key=tar_filename,
                        UploadId=upload_id,
                    )
                )
            except BotoCoreError:
                _LOGGER.exception("Failed to abort multipart upload")
            raise

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
        await self._hass.async_add_executor_job(
            functools.partial(
                self._client.delete_object, Bucket=self._bucket, Key=tar_filename
            )
        )
        await self._hass.async_add_executor_job(
            functools.partial(
                self._client.delete_object, Bucket=self._bucket, Key=metadata_filename
            )
        )

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
        response = await self._hass.async_add_executor_job(
            functools.partial(
                self._client.list_objects_v2,
                Bucket=self._bucket,
            )
        )

        # Filter for metadata files only
        metadata_files = [
            obj
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".metadata.json")
        ]

        for metadata_file in metadata_files:
            try:
                # Download and parse metadata file
                metadata_response = await self._hass.async_add_executor_job(
                    functools.partial(
                        self._client.get_object,
                        Bucket=self._bucket,
                        Key=metadata_file["Key"],
                    )
                )
                metadata_content = await self._hass.async_add_executor_job(
                    metadata_response["Body"].read
                )
                metadata_json = json.loads(metadata_content)
            except (BotoCoreError, json.JSONDecodeError) as err:
                _LOGGER.warning(
                    "Failed to process metadata file %s: %s",
                    metadata_file["Key"],
                    err,
                )
                continue
            backup = AgentBackup.from_dict(metadata_json)
            backups[backup.backup_id] = backup

        self._backup_cache = backups
        self._cache_expiration = time() + CACHE_TTL

        return self._backup_cache
