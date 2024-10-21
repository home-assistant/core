"""The tests for local file camera component."""

from http import HTTPStatus
from typing import Any
from unittest.mock import Mock, mock_open, patch

import pytest

from homeassistant.components.local_file.const import (
    DEFAULT_NAME,
    DOMAIN,
    SERVICE_UPDATE_FILE_PATH,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_ENTITY_ID, CONF_FILE_PATH
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


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


async def test_file_not_readable_after_setup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test a warning is shown setup when file is not readable."""

    client = await hass_client()

    with patch(
        "homeassistant.components.local_file.camera.open", side_effect=FileNotFoundError
    ):
        resp = await client.get("/api/camera_proxy/camera.local_file")

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Could not read camera Local File image from file: mock.file" in caplog.text


@pytest.mark.parametrize(
    ("config", "url", "content_type"),
    [
        (
            {
                "name": "test_jpg",
                "file_path": "/path/to/image.jpg",
            },
            "/api/camera_proxy/camera.test_jpg",
            "image/jpeg",
        ),
        (
            {
                "name": "test_png",
                "file_path": "/path/to/image.png",
            },
            "/api/camera_proxy/camera.test_png",
            "image/png",
        ),
        (
            {
                "name": "test_svg",
                "file_path": "/path/to/image.svg",
            },
            "/api/camera_proxy/camera.test_svg",
            "image/svg+xml",
        ),
        (
            {
                "name": "test_no_ext",
                "file_path": "/path/to/image",
            },
            "/api/camera_proxy/camera.test_no_ext",
            "image/jpeg",
        ),
    ],
)
async def test_camera_content_type(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config: dict[str, Any],
    url: str,
    content_type: str,
) -> None:
    """Test local_file camera content_type."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
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
    [
        {
            "name": DEFAULT_NAME,
            "file_path": "mock/path.jpg",
        }
    ],
)
async def test_update_file_path(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test update_file_path service."""
    # Setup platform
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        options={
            "name": "local_file_camera_2",
            "file_path": "mock/path_2.jpg",
        },
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


async def test_import_from_yaml_success(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import."""

    with (
        patch("os.path.isfile", Mock(return_value=True)),
        patch("os.access", Mock(return_value=True)),
        patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            Mock(return_value=(None, None)),
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

    assert hass.config_entries.async_has_entries(DOMAIN)
    state = hass.states.get("camera.config_test")
    assert state.attributes.get("file_path") == "mock.file"

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue
    assert issue.translation_key == "deprecated_yaml"


async def test_import_from_yaml_fails(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import fails due to not accessible file."""

    with (
        patch("os.path.isfile", Mock(return_value=True)),
        patch("os.access", Mock(return_value=False)),
        patch(
            "homeassistant.components.local_file.camera.mimetypes.guess_type",
            Mock(return_value=(None, None)),
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

    assert not hass.config_entries.async_has_entries(DOMAIN)
    assert not hass.states.get("camera.config_test")

    issue = issue_registry.async_get_issue(
        DOMAIN, f"no_access_path_{slugify("mock.file")}"
    )
    assert issue
    assert issue.translation_key == "no_access_path"
