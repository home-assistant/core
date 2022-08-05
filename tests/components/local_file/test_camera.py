"""The tests for local file camera component."""
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from unittest.mock import mock_open, patch

from aiohttp import ClientSession
import pytest

from homeassistant.components.local_file.const import DOMAIN, SERVICE_UPDATE_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_loading_file(hass: HomeAssistant, hass_client) -> None:
    """Test that it loads image from disk."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch("os.access", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client()

    m_open = mock_open(read_data=b"hello")
    with patch("homeassistant.components.local_file.camera.open", m_open, create=True):
        resp = await client.get("/api/camera_proxy/camera.local_file")

    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "hello"


async def test_file_not_readable(
    hass: HomeAssistant,
    hass_client: Callable[..., Awaitable[ClientSession]],
    caplog: pytest.LogCaptureFixture,
):
    """Test when fetching file fails."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch("os.access", return_value=True), patch(
        "homeassistant.components.local_file.camera.mimetypes.guess_type",
        return_value=(None, None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client()

    await client.get("/api/camera_proxy/camera.local_file")
    assert "Could not read" in caplog.text
    assert "Local File" in caplog.text
    assert "file.jpg" in caplog.text


async def test_camera_content_type(
    hass: HomeAssistant, hass_client: Callable[..., Awaitable[ClientSession]]
) -> None:
    """Test local_file camera content_type."""
    cam_config_jpg = {
        "name": "test_jpg",
        "platform": "local_file",
        "file_path": "/path/to/image.jpg",
    }
    cam_config_png = {
        "name": "test_png",
        "platform": "local_file",
        "file_path": "/path/to/image.png",
    }
    cam_config_svg = {
        "name": "test_svg",
        "platform": "local_file",
        "file_path": "/path/to/image.svg",
    }
    cam_config_noext = {
        "name": "test_no_ext",
        "platform": "local_file",
        "file_path": "/path/to/image",
    }

    with patch("os.access", return_value=True):
        await async_setup_component(
            hass,
            "camera",
            {
                "camera": [
                    cam_config_jpg,
                    cam_config_png,
                    cam_config_svg,
                    cam_config_noext,
                ]
            },
        )
        await hass.async_block_till_done()

    client = await hass_client()

    image = "hello"
    m_open = mock_open(read_data=image.encode())
    with patch("homeassistant.components.local_file.camera.open", m_open, create=True):
        resp_1 = await client.get("/api/camera_proxy/camera.test_jpg")
        resp_2 = await client.get("/api/camera_proxy/camera.test_png")
        resp_3 = await client.get("/api/camera_proxy/camera.test_svg")
        resp_4 = await client.get("/api/camera_proxy/camera.test_no_ext")

    assert resp_1.status == HTTPStatus.OK
    assert resp_1.content_type == "image/jpeg"
    body = await resp_1.text()
    assert body == image

    assert resp_2.status == HTTPStatus.OK
    assert resp_2.content_type == "image/png"
    body = await resp_2.text()
    assert body == image

    assert resp_3.status == HTTPStatus.OK
    assert resp_3.content_type == "image/svg+xml"
    body = await resp_3.text()
    assert body == image

    # default mime type
    assert resp_4.status == HTTPStatus.OK
    assert resp_4.content_type == "image/jpeg"
    body = await resp_4.text()
    assert body == image


async def test_update_file_path(hass: HomeAssistant) -> None:
    """Test update_file_path service."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch("os.access", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        if state := hass.states.get("camera.local_file"):
            assert state.attributes.get("friendly_name") == "Local File"
            assert state.attributes.get("file_path") == "/test/file.jpg"

        service_data = {"entity_id": "camera.local_file", "file_path": "new/path.jpg"}

        await hass.services.async_call(DOMAIN, SERVICE_UPDATE_FILE_PATH, service_data)
        await hass.async_block_till_done()

        if state := hass.states.get("camera.local_file"):
            assert state.attributes.get("file_path") == "new/path.jpg"

    # file path is not updated if file doesn't exist
    service_data = {"entity_id": "camera.local_file", "file_path": "invalid/path.jpg"}

    await hass.services.async_call(DOMAIN, SERVICE_UPDATE_FILE_PATH, service_data)
    await hass.async_block_till_done()

    if state := hass.states.get("camera.local_file"):
        assert state.attributes.get("file_path") == "new/path.jpg"
