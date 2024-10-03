"""The tests for local file camera component."""

from http import HTTPStatus
from unittest import mock

import pytest

from homeassistant.components.local_file.const import DOMAIN, SERVICE_UPDATE_FILE_PATH
from homeassistant.const import ATTR_ENTITY_ID, CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


async def test_loading_file(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that it loads image from disk."""
    with (
        mock.patch("os.path.isfile", mock.Mock(return_value=True)),
        mock.patch("os.access", mock.Mock(return_value=True)),
        mock.patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            mock.Mock(return_value=(None, None)),
        ),
    ):
        await async_setup_component(
            hass,
            "camera",
            {
                "camera": {
                    "name": "config_test",
                    "platform": "local_file",
                    "file_path": "mock.file",
                }
            },
        )
        await hass.async_block_till_done()

    client = await hass_client()

    m_open = mock.mock_open(read_data=b"hello")
    with mock.patch(
        "homeassistant.components.local_file.camera.open", m_open, create=True
    ):
        resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "hello"


async def test_file_not_readable(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a warning is shown setup when file is not readable."""
    with (
        mock.patch("os.path.isfile", mock.Mock(return_value=True)),
        mock.patch("os.access", mock.Mock(return_value=False)),
    ):
        await async_setup_component(
            hass,
            "camera",
            {
                "camera": {
                    "name": "config_test",
                    "platform": "local_file",
                    "file_path": "mock.file",
                }
            },
        )
        await hass.async_block_till_done()

    assert "File path mock.file is not readable;" in caplog.text


async def test_file_not_readable_after_setup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a warning is shown setup when file is not readable."""
    with (
        mock.patch("os.path.isfile", mock.Mock(return_value=True)),
        mock.patch("os.access", mock.Mock(return_value=True)),
        mock.patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            mock.Mock(return_value=(None, None)),
        ),
    ):
        await async_setup_component(
            hass,
            "camera",
            {
                "camera": {
                    "name": "config_test",
                    "platform": "local_file",
                    "file_path": "mock.file",
                }
            },
        )
        await hass.async_block_till_done()

    client = await hass_client()

    with mock.patch(
        "homeassistant.components.local_file.camera.open", side_effect=FileNotFoundError
    ):
        resp = await client.get("/api/camera_proxy/camera.config_test")

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Could not read camera config_test image from file: mock.file" in caplog.text


async def test_camera_content_type(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
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
    with (
        mock.patch("os.path.isfile", mock.Mock(return_value=True)),
        mock.patch("os.access", mock.Mock(return_value=True)),
    ):
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
    m_open = mock.mock_open(read_data=image.encode())
    with mock.patch(
        "homeassistant.components.local_file.camera.open", m_open, create=True
    ):
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
    # Setup platform
    with (
        mock.patch("os.path.isfile", mock.Mock(return_value=True)),
        mock.patch("os.access", mock.Mock(return_value=True)),
        mock.patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            mock.Mock(return_value=(None, None)),
        ),
    ):
        camera_1 = {"platform": "local_file", "file_path": "mock/path.jpg"}
        camera_2 = {
            "platform": "local_file",
            "name": "local_file_camera_2",
            "file_path": "mock/path_2.jpg",
        }
        await async_setup_component(hass, "camera", {"camera": [camera_1, camera_2]})
        await hass.async_block_till_done()

        # Fetch state and check motion detection attribute
        state = hass.states.get("camera.local_file")
        assert state.attributes.get("friendly_name") == "Local File"
        assert state.attributes.get("file_path") == "mock/path.jpg"

        service_data = {"entity_id": "camera.local_file", "file_path": "new/path.jpg"}

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_FILE_PATH,
            service_data,
            blocking=True,
        )

        state = hass.states.get("camera.local_file")
        assert state.attributes.get("file_path") == "new/path.jpg"

        # Check that local_file_camera_2 file_path is still as configured
        state = hass.states.get("camera.local_file_camera_2")
        assert state.attributes.get("file_path") == "mock/path_2.jpg"

    # Assert it fails if file is not readable
    service_data = {
        ATTR_ENTITY_ID: "camera.local_file",
        CONF_FILE_PATH: "new/path2.jpg",
    }
    with pytest.raises(
        ServiceValidationError, match="Path new/path2.jpg is not accessible"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_FILE_PATH,
            service_data,
            blocking=True,
        )
