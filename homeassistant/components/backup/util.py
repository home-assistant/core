"""Local backup support for Core and Container installations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from concurrent.futures import CancelledError, Future
import copy
from dataclasses import dataclass, replace
from io import BytesIO
import json
import os
from pathlib import Path, PurePath
from queue import SimpleQueue
import tarfile
import threading
from typing import IO, Any, Self, cast

import aiohttp
from securetar import SecureTarError, SecureTarFile, SecureTarReadError

from homeassistant.backup_restore import password_to_key
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import BUF_SIZE, LOGGER
from .models import AddonInfo, AgentBackup, Folder


class DecryptError(HomeAssistantError):
    """Error during decryption."""

    _message = "Unexpected error during decryption."


class EncryptError(HomeAssistantError):
    """Error during encryption."""

    _message = "Unexpected error during encryption."


class UnsupportedSecureTarVersion(DecryptError):
    """Unsupported securetar version."""

    _message = "Unsupported securetar version."


class IncorrectPassword(DecryptError):
    """Invalid password or corrupted backup."""

    _message = "Invalid password or corrupted backup."


class BackupEmpty(DecryptError):
    """No tar files found in the backup."""

    _message = "No tar files found in the backup."


class AbortCipher(HomeAssistantError):
    """Abort the cipher operation."""

    _message = "Abort cipher operation."


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

        extra_metadata = cast(dict[str, bool | str], data.get("extra", {}))
        date = extra_metadata.get("supervisor.backup_request_date", data["date"])

        return AgentBackup(
            addons=addons,
            backup_id=cast(str, data["slug"]),
            database_included=database_included,
            date=cast(str, date),
            extra_metadata=extra_metadata,
            folders=folders,
            homeassistant_included=homeassistant_included,
            homeassistant_version=homeassistant_version,
            name=cast(str, data["name"]),
            protected=cast(bool, data.get("protected", False)),
            size=backup_path.stat().st_size,
        )


def suggested_filename_from_name_date(name: str, date_str: str) -> str:
    """Suggest a filename for the backup."""
    date = dt_util.parse_datetime(date_str, raise_on_error=True)
    return "_".join(f"{name} {date.strftime('%Y-%m-%d %H.%M %S%f')}.tar".split())


def suggested_filename(backup: AgentBackup) -> str:
    """Suggest a filename for the backup."""
    return suggested_filename_from_name_date(backup.name, backup.date)


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
        self._aborted = False
        self._hass = hass
        self._stream = stream
        self._buffer: bytes | None = None
        self._next_future: Future[bytes | None] | None = None
        self._pos: int = 0

    async def _next(self) -> bytes | None:
        """Get the next chunk from the iterator."""
        return await anext(self._stream, None)

    def abort(self) -> None:
        """Abort the reader."""
        self._aborted = True
        if self._next_future is not None:
            self._next_future.cancel()

    def read(self, n: int = -1, /) -> bytes:
        """Read data from the iterator."""
        result = bytearray()
        while n < 0 or len(result) < n:
            if not self._buffer:
                self._next_future = asyncio.run_coroutine_threadsafe(
                    self._next(), self._hass.loop
                )
                if self._aborted:
                    self._next_future.cancel()
                    raise AbortCipher
                try:
                    self._buffer = self._next_future.result()
                except CancelledError as err:
                    raise AbortCipher from err
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
        self._aborted = False
        self._hass = hass
        self._pos: int = 0
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)
        self._write_future: Future[bytes | None] | None = None

    def __aiter__(self) -> Self:
        """Return the iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Get the next chunk from the iterator."""
        if data := await self._queue.get():
            return data
        raise StopAsyncIteration

    def abort(self) -> None:
        """Abort the writer."""
        self._aborted = True
        if self._write_future is not None:
            self._write_future.cancel()

    def tell(self) -> int:
        """Return the current position in the iterator."""
        return self._pos

    def write(self, s: bytes, /) -> int:
        """Write data to the iterator."""
        self._write_future = asyncio.run_coroutine_threadsafe(
            self._queue.put(s), self._hass.loop
        )
        if self._aborted:
            self._write_future.cancel()
            raise AbortCipher
        try:
            self._write_future.result()
        except CancelledError as err:
            raise AbortCipher from err
        self._pos += len(s)
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


def _get_expected_archives(backup: AgentBackup) -> set[str]:
    """Get the expected archives in the backup."""
    expected_archives = set()
    if backup.homeassistant_included:
        expected_archives.add("homeassistant")
    for addon in backup.addons:
        expected_archives.add(addon.slug)
    for folder in backup.folders:
        expected_archives.add(folder.value)
    return expected_archives


def decrypt_backup(
    backup: AgentBackup,
    input_stream: IO[bytes],
    output_stream: IO[bytes],
    password: str | None,
    on_done: Callable[[Exception | None], None],
    minimum_size: int,
    nonces: NonceGenerator,
) -> None:
    """Decrypt a backup."""
    error: Exception | None = None
    try:
        try:
            with (
                tarfile.open(
                    fileobj=input_stream, mode="r|", bufsize=BUF_SIZE
                ) as input_tar,
                tarfile.open(
                    fileobj=output_stream, mode="w|", bufsize=BUF_SIZE
                ) as output_tar,
            ):
                _decrypt_backup(backup, input_tar, output_tar, password)
        except (DecryptError, SecureTarError, tarfile.TarError) as err:
            LOGGER.warning("Error decrypting backup: %s", err)
            error = err
        else:
            # Pad the output stream to the requested minimum size
            padding = max(minimum_size - output_stream.tell(), 0)
            output_stream.write(b"\0" * padding)
        finally:
            # Write an empty chunk to signal the end of the stream
            output_stream.write(b"")
    except AbortCipher:
        LOGGER.debug("Cipher operation aborted")
    finally:
        on_done(error)


def _decrypt_backup(
    backup: AgentBackup,
    input_tar: tarfile.TarFile,
    output_tar: tarfile.TarFile,
    password: str | None,
) -> None:
    """Decrypt a backup."""
    expected_archives = _get_expected_archives(backup)
    for obj in input_tar:
        # We compare with PurePath to avoid issues with different path separators,
        # for example when backup.json is added as "./backup.json"
        object_path = PurePath(obj.name)
        if object_path == PurePath("backup.json"):
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
        prefix, _, suffix = object_path.name.partition(".")
        if suffix not in ("tar", "tgz", "tar.gz"):
            LOGGER.debug("Unknown file %s will not be decrypted", obj.name)
            output_tar.addfile(obj, input_tar.extractfile(obj))
            continue
        if prefix not in expected_archives:
            LOGGER.debug("Unknown inner tar file %s will not be decrypted", obj.name)
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


def encrypt_backup(
    backup: AgentBackup,
    input_stream: IO[bytes],
    output_stream: IO[bytes],
    password: str | None,
    on_done: Callable[[Exception | None], None],
    minimum_size: int,
    nonces: NonceGenerator,
) -> None:
    """Encrypt a backup."""
    error: Exception | None = None
    try:
        try:
            with (
                tarfile.open(
                    fileobj=input_stream, mode="r|", bufsize=BUF_SIZE
                ) as input_tar,
                tarfile.open(
                    fileobj=output_stream, mode="w|", bufsize=BUF_SIZE
                ) as output_tar,
            ):
                _encrypt_backup(backup, input_tar, output_tar, password, nonces)
        except (EncryptError, SecureTarError, tarfile.TarError) as err:
            LOGGER.warning("Error encrypting backup: %s", err)
            error = err
        else:
            # Pad the output stream to the requested minimum size
            padding = max(minimum_size - output_stream.tell(), 0)
            output_stream.write(b"\0" * padding)
        finally:
            # Write an empty chunk to signal the end of the stream
            output_stream.write(b"")
    except AbortCipher:
        LOGGER.debug("Cipher operation aborted")
    finally:
        on_done(error)


def _encrypt_backup(
    backup: AgentBackup,
    input_tar: tarfile.TarFile,
    output_tar: tarfile.TarFile,
    password: str | None,
    nonces: NonceGenerator,
) -> None:
    """Encrypt a backup."""
    inner_tar_idx = 0
    expected_archives = _get_expected_archives(backup)
    for obj in input_tar:
        # We compare with PurePath to avoid issues with different path separators,
        # for example when backup.json is added as "./backup.json"
        object_path = PurePath(obj.name)
        if object_path == PurePath("backup.json"):
            # Rewrite the backup.json file to indicate that the backup is encrypted
            if not (reader := input_tar.extractfile(obj)):
                raise EncryptError
            metadata = json_loads_object(reader.read())
            metadata["protected"] = True
            updated_metadata_b = json.dumps(metadata).encode()
            metadata_obj = copy.deepcopy(obj)
            metadata_obj.size = len(updated_metadata_b)
            output_tar.addfile(metadata_obj, BytesIO(updated_metadata_b))
            continue
        prefix, _, suffix = object_path.name.partition(".")
        if suffix not in ("tar", "tgz", "tar.gz"):
            LOGGER.debug("Unknown file %s will not be encrypted", obj.name)
            output_tar.addfile(obj, input_tar.extractfile(obj))
            continue
        if prefix not in expected_archives:
            LOGGER.debug("Unknown inner tar file %s will not be encrypted", obj.name)
            continue
        istf = SecureTarFile(
            None,  # Not used
            gzip=False,
            key=password_to_key(password) if password is not None else None,
            mode="r",
            fileobj=input_tar.extractfile(obj),
            nonce=nonces.get(inner_tar_idx),
        )
        inner_tar_idx += 1
        with istf.encrypt(obj) as encrypted:
            encrypted_obj = copy.deepcopy(obj)
            encrypted_obj.size = encrypted.encrypted_size
            output_tar.addfile(encrypted_obj, encrypted)


@dataclass(kw_only=True)
class _CipherWorkerStatus:
    done: asyncio.Event
    error: Exception | None = None
    reader: AsyncIteratorReader
    thread: threading.Thread
    writer: AsyncIteratorWriter


class NonceGenerator:
    """Generate nonces for encryption."""

    def __init__(self) -> None:
        """Initialize the generator."""
        self._nonces: dict[int, bytes] = {}

    def get(self, index: int) -> bytes:
        """Get a nonce for the given index."""
        if index not in self._nonces:
            # Generate a new nonce for the given index
            self._nonces[index] = os.urandom(16)
        return self._nonces[index]


class _CipherBackupStreamer:
    """Encrypt or decrypt a backup."""

    _cipher_func: Callable[
        [
            AgentBackup,
            IO[bytes],
            IO[bytes],
            str | None,
            Callable[[Exception | None], None],
            int,
            NonceGenerator,
        ],
        None,
    ]

    def __init__(
        self,
        hass: HomeAssistant,
        backup: AgentBackup,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        password: str | None,
    ) -> None:
        """Initialize."""
        self._workers: list[_CipherWorkerStatus] = []
        self._backup = backup
        self._hass = hass
        self._open_stream = open_stream
        self._password = password
        self._nonces = NonceGenerator()

    def size(self) -> int:
        """Return the maximum size of the decrypted or encrypted backup."""
        return self._backup.size + self._num_tar_files() * tarfile.RECORDSIZE

    def _num_tar_files(self) -> int:
        """Return the number of inner tar files."""
        b = self._backup
        return len(b.addons) + len(b.folders) + b.homeassistant_included + 1

    async def open_stream(self) -> AsyncIterator[bytes]:
        """Open a stream."""

        def on_done(error: Exception | None) -> None:
            """Call by the worker thread when it's done."""
            worker_status.error = error
            self._hass.loop.call_soon_threadsafe(worker_status.done.set)

        stream = await self._open_stream()
        reader = AsyncIteratorReader(self._hass, stream)
        writer = AsyncIteratorWriter(self._hass)
        worker = threading.Thread(
            target=self._cipher_func,
            args=[
                self._backup,
                reader,
                writer,
                self._password,
                on_done,
                self.size(),
                self._nonces,
            ],
        )
        worker_status = _CipherWorkerStatus(
            done=asyncio.Event(), reader=reader, thread=worker, writer=writer
        )
        self._workers.append(worker_status)
        worker.start()
        return writer

    async def wait(self) -> None:
        """Wait for the worker threads to finish."""
        for worker in self._workers:
            worker.reader.abort()
            worker.writer.abort()
        await asyncio.gather(*(worker.done.wait() for worker in self._workers))


class DecryptedBackupStreamer(_CipherBackupStreamer):
    """Decrypt a backup."""

    _cipher_func = staticmethod(decrypt_backup)

    def backup(self) -> AgentBackup:
        """Return the decrypted backup."""
        return replace(self._backup, protected=False, size=self.size())


class EncryptedBackupStreamer(_CipherBackupStreamer):
    """Encrypt a backup."""

    _cipher_func = staticmethod(encrypt_backup)

    def backup(self) -> AgentBackup:
        """Return the encrypted backup."""
        return replace(self._backup, protected=True, size=self.size())


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
