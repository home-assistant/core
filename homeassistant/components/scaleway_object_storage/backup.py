"""BackupAgent implementation based on Scaleway Object Storage."""

import asyncio
from dataclasses import dataclass
import hashlib
from http import HTTPStatus
import json
import logging
from typing import TYPE_CHECKING, Any, Self

import aiohttp
from aiohttp import ClientConnectionError
from aiohttp_s3_client.client import AwsUploadError, MultipartUploader, S3Client

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgent,
    BackupReaderWriterError,
    OnProgressCallback,
    suggested_filename,
)
from homeassistant.core import HomeAssistant, callback

from . import exceptions, helpers
from .const import (
    CONF_OBJECT_PREFIX,
    CONTENT_TYPE_TAR,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    HEADER_CONTENT_DISPOSITION,
    HEADER_CONTENT_TYPE,
    HEADER_METADATA,
    MAX_PARALLEL_HEAD_REQUESTS,
    MAX_PARALLEL_UPLOADS,
    MULTIPART_MIN_SIZE,
    MULTIPART_PART_SIZE,
)

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        AsyncIterator,
        Awaitable,
        Callable,
        Coroutine,
    )

    from . import ScalewayConfigEntry

    type OpenStream = Callable[[], Awaitable[AsyncIterator[bytes]]]
    type UploadJob = tuple[_Part, Coroutine[None, None, None]]

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class _Part:
    """A part of a multipart upload."""

    data: bytes
    digest: str

    @property
    def size(self) -> int:
        return len(self.data)

    @classmethod
    def from_data(cls, /, data: bytes) -> Self:
        """Creates a Part object based on the raw byte data.

        Automatically creates a sha256 digest of the data for the subsequent upload.
        """
        return cls(
            data=data,
            digest=hashlib.sha256(data).hexdigest(),
        )


class _ProgressTracker:
    def __init__(self, on_progress: OnProgressCallback) -> None:
        self._on_progress = on_progress
        self._lock = asyncio.Lock()
        self._progress = 0

    async def report_done(self, part: _Part) -> None:
        async with self._lock:
            self._progress += part.size
            self._on_progress(bytes_uploaded=self._progress)


async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    entries: list[ScalewayConfigEntry] = hass.config_entries.async_loaded_entries(
        DOMAIN
    )
    if not entries:
        _LOGGER.debug("No config entries loaded")
        return []

    return [ScalewayBackupAgent(hass, entry) for entry in entries]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed.

    Returns:
      A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)
        if not hass.data[DATA_BACKUP_AGENT_LISTENERS]:
            del hass.data[DATA_BACKUP_AGENT_LISTENERS]

    return remove_listener


class ScalewayBackupAgent(BackupAgent):
    """BackupAgent implementation that stores backups as objects in Scaleway Object Storage.

    Object keys are solely based on the backup ID to enable lookups without having to list all objects.
    """

    domain = DOMAIN

    def __init__(self, hass: HomeAssistant, entry: ScalewayConfigEntry) -> None:
        """Create a new instance of the BackupAgent based on a config entry."""
        super().__init__()
        self.name = entry.title
        self.unique_id = entry.entry_id

        self._hass = hass
        self._entry = entry
        self._prefix: str = entry.data[CONF_OBJECT_PREFIX]

    @property
    def _client(self) -> S3Client:
        return self._entry.runtime_data

    def _calculate_object_key(self, backup_id: str) -> str:
        prefix = self._prefix
        object_key = f"home-assistant-backup-{backup_id}.tar"
        if prefix:
            return f"{prefix}{object_key}"

        return object_key

    @staticmethod
    async def _yield_chunks(response: aiohttp.ClientResponse) -> AsyncGenerator[bytes]:
        """Yields byte chunks of arbitrary size from a response body, then closes the response."""
        try:
            content = response.content
            async for chunk in content.iter_any():
                yield chunk
        finally:
            response.release()

    async def async_download_backup(
        self, backup_id: str, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        Raises BackupNotFound if the backup does not exist.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """
        object_key = self._calculate_object_key(backup_id)

        try:
            response = await self._client.get(
                object_name=object_key,
            )
        except ClientConnectionError as e:
            raise exceptions.ScalewayConnectionError from e

        if response.status == HTTPStatus.NOT_FOUND:
            response.release()
            raise exceptions.ObjectNotFoundException(object_key=object_key)

        try:
            helpers.raise_for_status(response.status)
        except Exception:
            response.release()
            raise

        return self._yield_chunks(response)

    async def async_upload_backup(
        self,
        *,
        open_stream: OpenStream,
        backup: AgentBackup,
        on_progress: OnProgressCallback,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param open_stream: A function returning an async iterator that yields bytes.
        :param backup: Metadata about the backup that should be uploaded.
        :param on_progress: A callback to report the number of uploaded bytes.
        """
        if backup.size < MULTIPART_MIN_SIZE:
            await self._upload_object(backup=backup, open_stream=open_stream)
            on_progress(bytes_uploaded=backup.size)
        else:
            await self._upload_multipart_object(
                backup=backup,
                open_stream=open_stream,
                progress_tracker=_ProgressTracker(on_progress),
            )

    @staticmethod
    def _create_headers(backup: AgentBackup) -> dict[str, str]:
        """Creates the headers that will be sent as metadata when uploading the backup to object storage."""
        return {
            HEADER_CONTENT_DISPOSITION: f'attachment; filename="{suggested_filename(backup)}"',
            HEADER_CONTENT_TYPE: CONTENT_TYPE_TAR,
            # Would be neat to add all keys of the backup dict as separate metadata keys,
            # but only string values are accepted by S3. Converting to string would make
            # parsing back to a AgentBackup object difficult (see async_get_backup).
            HEADER_METADATA: json.dumps(backup.as_dict()),
        }

    async def _upload_object(
        self,
        *,
        open_stream: OpenStream,
        backup: AgentBackup,
    ) -> None:
        _LOGGER.debug("Uploading backup as single part")
        object_key = self._calculate_object_key(backup.backup_id)
        stream = await open_stream()
        try:
            response = await self._client.put(
                object_name=object_key,
                data=stream,
                data_length=backup.size,
                headers=self._create_headers(backup),
            )
        except ClientConnectionError as e:
            raise exceptions.ScalewayConnectionError from e

        try:
            helpers.raise_for_status(response.status)
        finally:
            response.release()

    @staticmethod
    async def _read_fixed_sized_parts(
        stream: AsyncIterator[bytes],
        *,
        part_size: int,
    ) -> AsyncGenerator[_Part]:
        """Takes a stream of byte chunks of arbitrary size and yields the data as evenly-sized chunks (except for the last chunk)."""
        buffer = bytearray()
        offset = 0

        async for chunk in stream:
            buffer.extend(chunk)
            with memoryview(buffer) as view:
                while len(buffer) - offset >= part_size:
                    end = offset + part_size
                    part_bytes = view[offset:end]
                    yield _Part.from_data(part_bytes.tobytes())
                    offset = end

            if offset and offset >= part_size:
                # compact buffer
                buffer = bytearray(buffer[offset:])
                offset = 0

        if offset < len(buffer):
            # We haven't reached the end of the buffer,
            # so we have a last chunk left in there that's smaller than the previous chunks.
            with memoryview(buffer) as view:
                yield _Part.from_data(view[offset:].tobytes())

    @staticmethod
    async def _consume_upload_queue(
        queue: asyncio.Queue[UploadJob],
        progress_tracker: _ProgressTracker,
    ) -> None:
        while True:
            try:
                part, upload = await queue.get()
            except asyncio.QueueShutDown:
                # Queue is empty, exit worker function
                return

            try:
                await upload
            except ClientConnectionError as e:
                _LOGGER.warning(
                    "Encountered connection error while uploading part",
                    exc_info=e,
                )
                queue.shutdown()
                raise exceptions.ScalewayConnectionError from e
            except AwsUploadError as e:
                _LOGGER.warning(
                    "Encountered exception while uploading part", exc_info=e
                )
                queue.shutdown()
                helpers.raise_for_status(e.status)

            await progress_tracker.report_done(part)
            queue.task_done()

    @staticmethod
    async def _clean_up_queue(queue: asyncio.Queue[UploadJob]) -> None:
        while not queue.empty():
            # Make sure we leave no dangling coroutines
            try:
                _, upload = queue.get_nowait()
                upload.close()
            except asyncio.QueueEmpty:
                # Queue is already empty (likely due to a race condition)
                return

    async def _upload_multipart_object(
        self,
        *,
        open_stream: OpenStream,
        progress_tracker: _ProgressTracker,
        backup: AgentBackup,
    ) -> None:
        _LOGGER.debug("Uploading backup as multiple parts")
        object_key = self._calculate_object_key(backup.backup_id)

        try:
            async with MultipartUploader(
                self._client,
                object_name=object_key,
                headers=self._create_headers(backup),
            ) as uploader:
                stream = await open_stream()

                # Queue size is limited to avoid pre-reading the parts into memory faster than we
                # can upload them.
                queue: asyncio.Queue[UploadJob] = asyncio.Queue(maxsize=1)
                workers: list[asyncio.Task[None]] = []

                # Start our upload workers
                for _ in range(MAX_PARALLEL_UPLOADS):
                    worker = asyncio.create_task(
                        self._consume_upload_queue(queue, progress_tracker)
                    )
                    workers.append(worker)

                # Create all parts
                upload: Coroutine[None, None, None]
                try:
                    async for part in self._read_fixed_sized_parts(
                        stream, part_size=MULTIPART_PART_SIZE
                    ):
                        # Creating the upload (assigning a number), but not awaiting it yet
                        upload = uploader.put_part(
                            data=part.data,
                            content_sha256=part.digest,
                        )
                        try:
                            await queue.put((part, upload))
                        except asyncio.QueueShutDown:
                            # An upload failed so the queue was shut down by the worker.
                            upload.close()
                            for worker in workers:
                                worker.cancel()
                            break

                    # All puts done, we can shut down the queue to signal workers
                    queue.shutdown()
                except Exception as e:
                    # We couldn't finish reading the input.
                    # Cancel the workers, clean up, then re-raise as integration exception.
                    for worker in workers:
                        worker.cancel()

                    await self._clean_up_queue(queue)
                    queue.shutdown()
                    raise BackupReaderWriterError from e

                done, pending = await asyncio.wait(
                    workers, return_when=asyncio.FIRST_EXCEPTION
                )

                for worker in pending:
                    # If any worker raised an exception, cancel the pending workers
                    worker.cancel()

                await self._clean_up_queue(queue)

                for worker in done:
                    # Raise the first exception we see
                    if task_exception := worker.exception():
                        raise task_exception

        except ClientConnectionError as e:
            raise exceptions.ScalewayConnectionError from e
        except AwsUploadError as e:
            # May happen during creation/completion of MultipartUpload (__aenter__, __aexit__ of MultipartUploader)
            _LOGGER.warning("Got exception while managing multipart upload", exc_info=e)
            helpers.raise_for_status(e.status)

    async def async_delete_backup(self, backup_id: str, **kwargs: Any) -> None:
        """Delete a backup file.

        Raises BackupNotFound if the backup does not exist.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """
        object_key = self._calculate_object_key(backup_id)

        try:
            response = await self._client.delete(object_name=object_key)
        except ClientConnectionError as e:
            raise exceptions.ScalewayConnectionError from e

        try:
            if response.status == HTTPStatus.NOT_FOUND:
                _LOGGER.info(
                    "Tried to delete object that doesn't exist: %s", object_key
                )
                # The object wasn't found. Since we were going to delete it anyway, that's fine.
                return
            helpers.raise_for_status(response.status)
        finally:
            response.release()

    async def _try_read_metadata(
        self, *, object_key: str, limiter: asyncio.Semaphore
    ) -> AgentBackup | None:
        try:
            return await helpers.read_object_metadata(
                client=self._client,
                object_key=object_key,
                limiter=limiter,
            )
        except exceptions.MissingMetadataException:
            # Assume we encountered an unrelated object.
            return None
        except exceptions.ObjectNotFoundException as e:
            _LOGGER.debug(
                "Unknown object was requested: %s",
                e.object_key,
            )
            # Likely caused by a race condition (object was deleted between listing and reading)
            return None

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        backups = []
        limiter = asyncio.Semaphore(MAX_PARALLEL_HEAD_REQUESTS)

        try:
            async with asyncio.TaskGroup() as tg:
                async for object_key in helpers.list_objects(
                    client=self._client, prefix=self._prefix
                ):
                    # Acquire the semaphore here to ensure we don't read too far ahead of
                    # the HEAD requests.
                    async with limiter:
                        task = tg.create_task(
                            self._try_read_metadata(
                                object_key=object_key, limiter=limiter
                            ),
                            # Eagerly start the task to make sure it acquires the semaphore.
                            eager_start=True,
                        )
                        backups.append(task)

        except* exceptions.ScalewayException as e:
            # Each task could raise a ScalewayException.
            task_exceptions = list(helpers.unpack_exception_group(e))
            if len(task_exceptions) > 1:
                _LOGGER.warning(
                    "Encountered multiple exceptions while listing backups, only re-reraising the first"
                )
            raise task_exceptions[0] from None

        # Get task results and filter out None values
        return list(filter(None, (task.result() for task in backups)))

    async def async_get_backup(self, backup_id: str, **kwargs: Any) -> AgentBackup:
        """Return a backup.

        Raises BackupNotFound if the backup does not exist.
        """
        object_key = self._calculate_object_key(backup_id)
        return await helpers.read_object_metadata(
            client=self._client, object_key=object_key, limiter=None
        )
