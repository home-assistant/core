"""Test the File Upload integration."""

import asyncio
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from random import getrandbits
import threading
from typing import Any, Self
from unittest.mock import AsyncMock, patch

from aiohttp import BodyPartReader
import pytest

from homeassistant.components import file_upload
from homeassistant.components.file_upload import DOMAIN, FileUploadView
from homeassistant.components.http import KEY_HASS
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.image_upload import TEST_IMAGE
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="uploaded_file_dir")
async def upload_file_dir(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> Path:
    """Test uploading and using a file."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()

    with (
        patch(
            # Patch temp dir name to avoid tests fail running in parallel
            "homeassistant.components.file_upload.TEMP_DIR_NAME",
            file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
        ),
        TEST_IMAGE.open("rb") as fp,
    ):
        res = await client.post("/api/file_upload", data={"file": fp})

    assert res.status == 200
    response = await res.json()

    file_dir = hass.data[file_upload.DOMAIN].file_dir(response["file_id"])
    assert file_dir.is_dir()
    return file_dir


async def test_using_file(hass: HomeAssistant, uploaded_file_dir) -> None:
    """Test uploading and using a file."""
    # Test we can use it
    with file_upload.process_uploaded_file(hass, uploaded_file_dir.name) as file_path:
        assert file_path.is_file()
        assert file_path.parent == uploaded_file_dir
        assert file_path.read_bytes() == TEST_IMAGE.read_bytes()

    assert not uploaded_file_dir.exists()


async def test_removing_file(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, uploaded_file_dir
) -> None:
    """Test uploading and using a file."""
    client = await hass_client()

    response = await client.delete(
        "/api/file_upload", json={"file_id": uploaded_file_dir.name}
    )
    assert response.status == 200

    # Test it's removed
    assert not uploaded_file_dir.exists()


async def test_removed_on_stop(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, uploaded_file_dir
) -> None:
    """Test uploading and using a file."""
    await hass.async_stop()

    # Test it's removed
    assert not uploaded_file_dir.exists()


async def test_upload_large_file(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, large_file_io
) -> None:
    """Test uploading large file."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()

    with (
        patch(
            # Patch temp dir name to avoid tests fail running in parallel
            "homeassistant.components.file_upload.TEMP_DIR_NAME",
            file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
        ),
        patch(
            # Patch one megabyte to 50 bytes to prevent having to use big files in tests
            "homeassistant.components.file_upload.ONE_MEGABYTE",
            50,
        ),
    ):
        res = await client.post("/api/file_upload", data={"file": large_file_io})

    assert res.status == 200
    response = await res.json()

    file_dir = hass.data[file_upload.DOMAIN].file_dir(response["file_id"])
    assert file_dir.is_dir()

    large_file_io.seek(0)
    with file_upload.process_uploaded_file(hass, file_dir.name) as file_path:
        assert file_path.is_file()
        assert file_path.parent == file_dir
        assert file_path.read_bytes() == large_file_io.read().encode("utf-8")


async def test_upload_with_wrong_key_fails(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, large_file_io
) -> None:
    """Test uploading fails."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()

    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.file_upload.TEMP_DIR_NAME",
        file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
    ):
        res = await client.post("/api/file_upload", data={"wrong_key": large_file_io})

    assert res.status == 400


async def test_upload_large_file_fails(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, large_file_io
) -> None:
    """Test uploading large file."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()

    @contextmanager
    def _mock_open(*args, **kwargs):
        yield MockPathOpen()

    class MockPathOpen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def write(self, data: bytes) -> None:
            raise OSError("Boom")

    with (
        patch(
            # Patch temp dir name to avoid tests fail running in parallel
            "homeassistant.components.file_upload.TEMP_DIR_NAME",
            file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
        ),
        patch(
            # Patch one megabyte to 50 bytes to prevent having to use big files in tests
            "homeassistant.components.file_upload.ONE_MEGABYTE",
            50,
        ),
        patch(
            "homeassistant.components.file_upload.Path.open", return_value=_mock_open()
        ),
    ):
        res = await client.post("/api/file_upload", data={"file": large_file_io})

    assert res.status == 500

    response = await res.content.read()

    assert b"Boom" in response


async def test_upload_stream_error_releases_lock(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    large_file_io: StringIO,
) -> None:
    """Test a mid-upload stream error propagates and releases the upload lock.

    Models a client disconnect: aiohttp raises from read_chunk when the
    connection is lost mid-transfer. If the queue consumer's terminating sentinel
    is skipped on the error path, awaiting the consumer deadlocks while holding
    the upload lock, wedging every later upload; this guards that regression.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()

    with (
        patch(
            # Patch temp dir name to avoid tests fail running in parallel
            "homeassistant.components.file_upload.TEMP_DIR_NAME",
            file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
        ),
        patch.object(
            BodyPartReader,
            "read_chunk",
            AsyncMock(
                side_effect=[b"partial", ConnectionResetError("Connection lost")]
            ),
        ),
    ):
        # Bound the request so a reintroduced deadlock fails fast instead of hanging
        async with asyncio.timeout(10):
            res = await client.post("/api/file_upload", data={"file": large_file_io})

    assert res.status == 500

    # The failed upload must not leave a partially written file orphaned on disk
    file_upload_data = hass.data[file_upload.DOMAIN]
    assert list(file_upload_data.temp_dir.iterdir()) == []

    # The upload lock must have been released: a subsequent normal upload succeeds
    large_file_io.seek(0)
    with patch(
        "homeassistant.components.file_upload.TEMP_DIR_NAME",
        file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
    ):
        async with asyncio.timeout(10):
            res = await client.post("/api/file_upload", data={"file": large_file_io})

    assert res.status == 200


async def test_upload_cancelled_releases_consumer(hass: HomeAssistant) -> None:
    """Test cancelling an upload mid-transfer does not deadlock the consumer.

    Driven at the view level because the test HTTP client cannot produce a true
    task cancellation mid-request. Without delivering the queue sentinel on the
    cancellation path, awaiting the consumer future would hang forever.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    view = FileUploadView()

    first_chunk_sent = asyncio.Event()
    blocked = asyncio.Event()  # never set, so the stream blocks until cancelled

    class _BlockingPart:
        """Fake BodyPartReader that blocks after yielding one chunk."""

        name = "file"
        filename = "blocking.bin"

        async def read_chunk(self, size: int) -> bytes:
            if first_chunk_sent.is_set():
                await blocked.wait()
                return b""
            first_chunk_sent.set()
            return b"chunk"

    part = _BlockingPart()

    class _Reader:
        async def next(self) -> _BlockingPart:
            return part

    class _Request:
        app = {KEY_HASS: hass}

        async def multipart(self) -> _Reader:
            return _Reader()

    with (
        patch(
            "homeassistant.components.file_upload.TEMP_DIR_NAME",
            file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
        ),
        patch("homeassistant.components.file_upload.BodyPartReader", _BlockingPart),
    ):
        task = asyncio.create_task(view._upload_file(_Request()))
        await first_chunk_sent.wait()
        task.cancel()
        # asyncio.wait does not cancel on timeout, so a deadlocked task stays
        # pending and the assertion fails fast instead of the run hanging.
        _done, pending = await asyncio.wait({task}, timeout=10)

    assert not pending
    with pytest.raises(asyncio.CancelledError):
        task.result()


async def test_receive_file_field_cancelled_while_joining_writer(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test a cancel while joining the writer waits for the writer to finish.

    A cancellation delivered while _receive_file_field is awaiting the executor
    writer (the whole field already streamed, sentinel queued) must not return
    until the writer thread has finished, so the caller's cleanup cannot race it.
    """
    file_path = tmp_path / "uploaded.bin"
    writing_started = asyncio.Event()
    release_writer = threading.Event()  # blocks the writer thread mid-write
    writes: list[bytes] = []
    blocked_once = False

    class _BlockingHandle:
        """A file handle whose first write parks the writer thread until released."""

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

        def write(self, data: bytes) -> int:
            nonlocal blocked_once
            if not blocked_once:
                blocked_once = True
                hass.loop.call_soon_threadsafe(writing_started.set)
                release_writer.wait()
            writes.append(bytes(data))
            return len(data)

    real_open = Path.open

    def _blocking_open(self: Path, *args: object, **kwargs: object) -> object:
        if self != file_path:
            return real_open(self, *args, **kwargs)
        return _BlockingHandle()

    chunks = iter([b"chunk1", b"chunk2"])

    class _Part:
        """Fake BodyPartReader yielding two chunks then EOF."""

        async def read_chunk(self, size: int) -> bytes:
            return next(chunks, b"")

    with patch.object(Path, "open", _blocking_open):
        task = asyncio.create_task(
            file_upload._receive_file_field(hass, _Part(), file_path)
        )
        try:
            # The writer thread is now blocked on its first write, so the task has
            # queued every chunk plus the sentinel and is parked at the join; let it
            # settle there so the cancel lands on the join.
            await writing_started.wait()
            for _ in range(3):
                await asyncio.sleep(0)
            task.cancel()
            for _ in range(10):
                await asyncio.sleep(0)
            # Without the cancellation-safe join the task would finish here (returning
            # while the writer thread runs on); the fix keeps it waiting for the writer.
            assert not task.done()
        finally:
            # Always release the writer so a failed assertion can't leak the blocked
            # thread and hang teardown.
            release_writer.set()
        _done, pending = await asyncio.wait({task}, timeout=10)

    assert not pending
    with pytest.raises(asyncio.CancelledError):
        task.result()
    # The writer finished writing both chunks before the cancellation propagated.
    assert b"".join(writes) == b"chunk1chunk2"
