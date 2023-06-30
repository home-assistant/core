"""Test the File Upload integration."""
from pathlib import Path
from random import getrandbits
from unittest.mock import patch

import pytest

from homeassistant.components import file_upload
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.image_upload import TEST_IMAGE
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def uploaded_file_dir(hass: HomeAssistant, hass_client) -> Path:
    """Test uploading and using a file."""
    assert await async_setup_component(hass, "file_upload", {})
    client = await hass_client()

    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.file_upload.TEMP_DIR_NAME",
        file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
    ), TEST_IMAGE.open("rb") as fp:
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

    # Test it's removed
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
    assert await async_setup_component(hass, "file_upload", {})
    client = await hass_client()

    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.file_upload.TEMP_DIR_NAME",
        file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
    ), patch(
        # Patch one megabyte to 8 bytes to prevent having to use big files in tests
        "homeassistant.components.file_upload.ONE_MEGABYTE",
        8,
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
    assert await async_setup_component(hass, "file_upload", {})
    client = await hass_client()

    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.file_upload.TEMP_DIR_NAME",
        file_upload.TEMP_DIR_NAME + f"-{getrandbits(10):03x}",
    ):
        res = await client.post("/api/file_upload", data={"wrong_key": large_file_io})

    assert res.status == 400
