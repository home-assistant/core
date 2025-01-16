"""Local backup support for Core and Container installations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
import copy
from io import BytesIO
import json
from pathlib import Path, PurePath
from queue import SimpleQueue
import tarfile
from typing import IO, Self, cast

import aiohttp
from securetar import SecureTarError, SecureTarFile, SecureTarReadError

from homeassistant.backup_restore import password_to_key
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import BUF_SIZE, LOGGER
from .models import AddonInfo, AgentBackup, Folder


class DecryptError(HomeAssistantError):
    """Error during decryption."""

    _message = "Unexpected error during decryption."


class UnsupportedSecureTarVersion(DecryptError):
    """Unsupported securetar version."""

    _message = "Unsupported securetar version."


class IncorrectPassword(DecryptError):
    """Invalid password or corrupted backup."""

    _message = "Invalid password or corrupted backup."


class BackupEmpty(DecryptError):
    """No tar files found in the backup."""

    _message = "No tar files found in the backup."


def make_backup_dir(path: Path) -> None:
    """Create a backup directory if it does not exist."""
    path.mkdir(exist_ok=True)


def read_backup(backup_path: Path) -> AgentBackup:
    """Read a backup from disk."""

    with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
        if not (data_file := backup_file.extractfile("./backup.json")):
            raise KeyError("backup.json not found in tar file")
        data = json_loads_object(data_file.read())
        addons = [
            AddonInfo(
                name=cast(str, addon["name"]),
                slug=cast(str, addon["slug"]),
                version=cast(str, addon["version"]),
            )
            for addon in cast(list[JsonObjectType], data.get("addons", []))
        ]

        folders = [
            Folder(folder)
            for folder in cast(list[str], data.get("folders", []))
            if folder != "homeassistant"
        ]

        homeassistant_included = False
        homeassistant_version: str | None = None
        database_included = False
        if (
            homeassistant := cast(JsonObjectType, data.get("homeassistant"))
        ) and "version" in homeassistant:
            homeassistant_included = True
            homeassistant_version = cast(str, homeassistant["version"])
            database_included = not cast(
                bool, homeassistant.get("exclude_database", False)
            )

        return AgentBackup(
            addons=addons,
            backup_id=cast(str, data["slug"]),
            database_included=database_included,
            date=cast(str, data["date"]),
            extra_metadata=cast(dict[str, bool | str], data.get("extra", {})),
            folders=folders,
            homeassistant_included=homeassistant_included,
            homeassistant_version=homeassistant_version,
            name=cast(str, data["name"]),
            protected=cast(bool, data.get("protected", False)),
            size=backup_path.stat().st_size,
        )


def validate_password(path: Path, password: str | None) -> bool:
    """Validate the password."""
    with tarfile.open(path, "r:", bufsize=BUF_SIZE) as backup_file:
        compressed = False
        ha_tar_name = "homeassistant.tar"
        try:
            ha_tar = backup_file.extractfile(ha_tar_name)
        except KeyError:
            compressed = True
            ha_tar_name = "homeassistant.tar.gz"
            try:
                ha_tar = backup_file.extractfile(ha_tar_name)
            except KeyError:
                LOGGER.error("No homeassistant.tar or homeassistant.tar.gz found")
                return False
        try:
            with SecureTarFile(
                path,  # Not used
                gzip=compressed,
                key=password_to_key(password) if password is not None else None,
                mode="r",
                fileobj=ha_tar,
            ):
                # If we can read the tar file, the password is correct
                return True
        except tarfile.ReadError:
            LOGGER.debug("Invalid password")
            return False
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating password")
    return False


class AsyncIteratorReader:
    """Wrap an AsyncIterator."""

    def __init__(self, hass: HomeAssistant, stream: AsyncIterator[bytes]) -> None:
        """Initialize the wrapper."""
        self._hass = hass
        self._stream = stream
        self._buffer: bytes | None = None
        self._pos: int = 0

    async def _next(self) -> bytes | None:
        """Get the next chunk from the iterator."""
        return await anext(self._stream, None)

    def read(self, n: int = -1, /) -> bytes:
        """Read data from the iterator."""
        result = bytearray()
        while n < 0 or len(result) < n:
            if not self._buffer:
                self._buffer = asyncio.run_coroutine_threadsafe(
                    self._next(), self._hass.loop
                ).result()
                self._pos = 0
            if not self._buffer:
                # The stream is exhausted
                break
            chunk = self._buffer[self._pos : self._pos + n]
            result.extend(chunk)
            n -= len(chunk)
            self._pos += len(chunk)
            if self._pos == len(self._buffer):
                self._buffer = None
        return bytes(result)

    def close(self) -> None:
        """Close the iterator."""


class AsyncIteratorWriter:
    """Wrap an AsyncIterator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the wrapper."""
        self._hass = hass
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)

    def __aiter__(self) -> Self:
        """Return the iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Get the next chunk from the iterator."""
        if data := await self._queue.get():
            return data
        raise StopAsyncIteration

    def write(self, s: bytes, /) -> int:
        """Write data to the iterator."""
        asyncio.run_coroutine_threadsafe(self._queue.put(s), self._hass.loop).result()
        return len(s)


def validate_password_stream(
    input_stream: IO[bytes],
    password: str | None,
) -> None:
    """Decrypt a backup."""
    with (
        tarfile.open(fileobj=input_stream, mode="r|", bufsize=BUF_SIZE) as input_tar,
    ):
        for obj in input_tar:
            if not obj.name.endswith((".tar", ".tgz", ".tar.gz")):
                continue
            istf = SecureTarFile(
                None,  # Not used
                gzip=False,
                key=password_to_key(password) if password is not None else None,
                mode="r",
                fileobj=input_tar.extractfile(obj),
            )
            with istf.decrypt(obj) as decrypted:
                if istf.securetar_header.plaintext_size is None:
                    raise UnsupportedSecureTarVersion
                try:
                    decrypted.read(1)  # Read a single byte to trigger the decryption
                except SecureTarReadError as err:
                    raise IncorrectPassword from err
                return
    raise BackupEmpty


def decrypt_backup(
    input_stream: IO[bytes],
    output_stream: IO[bytes],
    password: str | None,
    on_done: Callable[[], None],
) -> None:
    """Decrypt a backup."""
    try:
        with (
            tarfile.open(
                fileobj=input_stream, mode="r|", bufsize=BUF_SIZE
            ) as input_tar,
            tarfile.open(
                fileobj=output_stream, mode="w|", bufsize=BUF_SIZE
            ) as output_tar,
        ):
            _decrypt_backup(input_tar, output_tar, password)
    except (DecryptError, SecureTarError, tarfile.TarError) as err:
        LOGGER.warning("Error decrypting backup: %s", err)
    finally:
        output_stream.write(b"")  # Write an empty chunk to signal the end of the stream
        on_done()


def _decrypt_backup(
    input_tar: tarfile.TarFile,
    output_tar: tarfile.TarFile,
    password: str | None,
) -> None:
    """Decrypt a backup."""
    for obj in input_tar:
        # We compare with PurePath to avoid issues with different path separators,
        # for example when backup.json is added as "./backup.json"
        if PurePath(obj.name) == PurePath("backup.json"):
            # Rewrite the backup.json file to indicate that the backup is decrypted
            if not (reader := input_tar.extractfile(obj)):
                raise DecryptError
            metadata = json_loads_object(reader.read())
            metadata["protected"] = False
            updated_metadata_b = json.dumps(metadata).encode()
            metadata_obj = copy.deepcopy(obj)
            metadata_obj.size = len(updated_metadata_b)
            output_tar.addfile(metadata_obj, BytesIO(updated_metadata_b))
            continue
        if not obj.name.endswith((".tar", ".tgz", ".tar.gz")):
            output_tar.addfile(obj, input_tar.extractfile(obj))
            continue
        istf = SecureTarFile(
            None,  # Not used
            gzip=False,
            key=password_to_key(password) if password is not None else None,
            mode="r",
            fileobj=input_tar.extractfile(obj),
        )
        with istf.decrypt(obj) as decrypted:
            if (plaintext_size := istf.securetar_header.plaintext_size) is None:
                raise UnsupportedSecureTarVersion
            decrypted_obj = copy.deepcopy(obj)
            decrypted_obj.size = plaintext_size
            output_tar.addfile(decrypted_obj, decrypted)


async def receive_file(
    hass: HomeAssistant, contents: aiohttp.BodyPartReader, path: Path
) -> None:
    """Receive a file from a stream and write it to a file."""
    queue: SimpleQueue[tuple[bytes, asyncio.Future[None] | None] | None] = SimpleQueue()

    def _sync_queue_consumer() -> None:
        with path.open("wb") as file_handle:
            while True:
                if (_chunk_future := queue.get()) is None:
                    break
                _chunk, _future = _chunk_future
                if _future is not None:
                    hass.loop.call_soon_threadsafe(_future.set_result, None)
                file_handle.write(_chunk)

    fut: asyncio.Future[None] | None = None
    try:
        fut = hass.async_add_executor_job(_sync_queue_consumer)
        megabytes_sending = 0
        while chunk := await contents.read_chunk(BUF_SIZE):
            megabytes_sending += 1
            if megabytes_sending % 5 != 0:
                queue.put_nowait((chunk, None))
                continue

            chunk_future = hass.loop.create_future()
            queue.put_nowait((chunk, chunk_future))
            await asyncio.wait(
                (fut, chunk_future),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if fut.done():
                # The executor job failed
                break

        queue.put_nowait(None)  # terminate queue consumer
    finally:
        if fut is not None:
            await fut
