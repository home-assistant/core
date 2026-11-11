"""The tests for local file camera component."""

import errno
from http import HTTPStatus
import os
from typing import Any
from unittest.mock import Mock, mock_open, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.camera import async_get_image
from homeassistant.components.local_file.const import DOMAIN
from homeassistant.components.local_file.services import (
    LocalFileService,
    LocalFileServiceArgument,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


async def test_loading_file(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test that it loads image from disk."""

    client = await hass_client()

    m_open = mock_open(read_data=b"hello")
    with patch("homeassistant.components.local_file.camera.open", m_open, create=True):
        resp = await client.get("/api/camera_proxy/camera.local_file")

    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "hello"


@pytest.mark.parametrize(
    ("error_no", "translation_key"),
    [
        pytest.param(errno.ENOENT, "os_read_not_found", id="not_found"),
        pytest.param(errno.EACCES, "os_read_permission_denied", id="permission"),
        pytest.param(errno.EISDIR, "os_read_is_directory", id="is_directory"),
        pytest.param(errno.EIO, "os_read_error", id="fallback"),
    ],
)
@pytest.mark.usefixtures("loaded_entry")
async def test_file_not_readable_after_setup(
    hass: HomeAssistant, error_no: int, translation_key: str
) -> None:
    """Test an error is raised when the file is not readable after setup."""
    with (
        patch(
            "homeassistant.components.local_file.camera.open",
            side_effect=OSError(error_no, os.strerror(error_no)),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await async_get_image(hass, "camera.local_file")

    assert exc_info.value.translation_domain == "homeassistant"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"path": "mock.file"}


@pytest.mark.parametrize(
    ("title", "config", "url", "content_type"),
    [
        (
            "test_jpg",
            {"file_path": "/path/to/image.jpg"},
            "/api/camera_proxy/camera.test_jpg",
            "image/jpeg",
        ),
        (
            "test_png",
            {"file_path": "/path/to/image.png"},
            "/api/camera_proxy/camera.test_png",
            "image/png",
        ),
        (
            "test_svg",
            {"file_path": "/path/to/image.svg"},
            "/api/camera_proxy/camera.test_svg",
            "image/svg+xml",
        ),
        (
            "test_no_ext",
            {"file_path": "/path/to/image"},
            "/api/camera_proxy/camera.test_no_ext",
            "image/jpeg",
        ),
    ],
)
async def test_camera_content_type(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    title: str,
    config: dict[str, Any],
    url: str,
    content_type: str,
) -> None:
    """Test local_file camera content_type."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title=title,
        options=config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)
    with (
        patch("os.path.isfile", Mock(return_value=True)),
        patch("os.access", Mock(return_value=True)),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client()

    image = "hello"
    m_open = mock_open(read_data=image.encode())
    with patch("homeassistant.components.local_file.camera.open", m_open, create=True):
        resp_1 = await client.get(url)

    assert resp_1.status == HTTPStatus.OK
    assert resp_1.content_type == content_type
    body = await resp_1.text()
    assert body == image


@pytest.mark.parametrize(
    "get_config",
    [{"file_path": "mock/path.jpg"}],
)
async def test_update_file_path(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test update_file_path service."""
    # Setup platform
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title="local_file_camera_2",
        options={"file_path": "mock/path_2.jpg"},
        entry_id="2",
    )

    config_entry.add_to_hass(hass)
    with (
        patch("os.path.isfile", Mock(return_value=True)),
        patch("os.access", Mock(return_value=True)),
        patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            Mock(return_value=(None, None)),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Fetch state and check motion detection attribute
    state = hass.states.get("camera.local_file")
    assert state.attributes.get("friendly_name") == "Local File"
    assert state.attributes.get("file_path") == "mock/path.jpg"

    service_data = {"entity_id": "camera.local_file", "file_path": "new/path.jpg"}

    with (
        patch("os.path.isfile", Mock(return_value=True)),
        patch("os.access", Mock(return_value=True)),
        patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            Mock(return_value=(None, None)),
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            LocalFileService.UPDATE_FILE_PATH,
            service_data,
            blocking=True,
        )

    await hass.async_block_till_done()

    state = hass.states.get("camera.local_file")
    assert state.attributes.get("file_path") == "new/path.jpg"

    # Check that local_file_camera_2 file_path is still as configured
    state = hass.states.get("camera.local_file_camera_2")
    assert state.attributes.get("file_path") == "mock/path_2.jpg"

    # Assert it fails if file is not readable
    service_data = {
        CommonServiceArgument.ENTITY_ID: "camera.local_file",
        LocalFileServiceArgument.FILE_PATH: "new/path2.jpg",
    }
    with pytest.raises(
        ServiceValidationError, match="Path new/path2.jpg is not accessible"
    ):
        await hass.services.async_call(
            DOMAIN,
            LocalFileService.UPDATE_FILE_PATH,
            service_data,
            blocking=True,
        )
