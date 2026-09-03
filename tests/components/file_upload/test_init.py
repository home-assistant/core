"""Test the File Upload integration."""

import asyncio
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from random import getrandbits
from typing import Any
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
