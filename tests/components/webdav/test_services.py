"""Tests for WebDAV services."""

from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, call, patch

from aiowebdav2.exceptions import (
    AccessDeniedError,
    ConnectionExceptionError,
    UnauthorizedError,
    WebDavError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.webdav.const import DOMAIN
from homeassistant.components.webdav.services import (
    CONF_DESTINATION_FOLDER,
    UPLOAD_SERVICE,
    UPLOAD_TIMEOUT,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration


@pytest.fixture(autouse=True)
def allow_tmp_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """Allow the services to read from the temporary directory."""
    hass.config.allowlist_external_dirs = {str(tmp_path)}


@pytest.fixture
def uploaded(webdav_client: AsyncMock) -> dict[str, bytes]:
    """Capture the bytes streamed to each remote path."""
    files: dict[str, bytes] = {}

    async def _write(path: str, data: AsyncIterable[bytes], **kwargs: Any) -> None:
        files[path] = b"".join([chunk async for chunk in data])

    webdav_client.write.side_effect = _write
    return files


async def _call_upload(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    filename: str | list[str],
    destination_folder: str,
) -> Any:
    return await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            CONF_FILENAME: filename,
            CONF_DESTINATION_FOLDER: destination_folder,
        },
        blocking=True,
        return_response=True,
    )


@patch("homeassistant.components.webdav.services.CHUNK_SIZE", 4)
async def test_upload_file(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    uploaded: dict[str, bytes],
) -> None:
    """Test uploading a single file in chunks."""
    content = b"doorbell snapshot bytes"
    (tmp_path / "snapshot.jpg").write_bytes(content)
    await setup_integration(hass, mock_config_entry)
    webdav_client.mkdir.reset_mock()

    response = await _call_upload(
        hass, mock_config_entry, str(tmp_path / "snapshot.jpg"), "/photos/snapshots/"
    )

    assert response == {"files": [{"path": "/photos/snapshots/snapshot.jpg"}]}
    webdav_client.mkdir.assert_called_once_with(
        "/photos/snapshots", parents=True, exist_ok=True
    )
    assert uploaded == {"/photos/snapshots/snapshot.jpg": content}
    assert webdav_client.write.call_args.kwargs == {
        "content_length": len(content),
        "timeout": UPLOAD_TIMEOUT,
    }


async def test_upload_to_root(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    uploaded: dict[str, bytes],
) -> None:
    """Test uploading to the server root does not create folders."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)
    webdav_client.mkdir.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        UPLOAD_SERVICE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            CONF_FILENAME: str(tmp_path / "snapshot.jpg"),
            CONF_DESTINATION_FOLDER: "/",
        },
        blocking=True,
    )

    webdav_client.mkdir.assert_not_called()
    assert uploaded == {"/snapshot.jpg": b"data"}


async def test_upload_wildcard(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    uploaded: dict[str, bytes],
) -> None:
    """Test uploading files matched by a wildcard recreates subfolders."""
    (tmp_path / "www" / "sub").mkdir(parents=True)
    (tmp_path / "www" / "a.jpg").write_bytes(b"a")
    (tmp_path / "www" / "sub" / "b.jpg").write_bytes(b"b")
    (tmp_path / "www" / "c.txt").write_bytes(b"c")
    await setup_integration(hass, mock_config_entry)
    webdav_client.mkdir.reset_mock()

    response = await _call_upload(
        hass, mock_config_entry, f"{tmp_path}/www/**/*.jpg", "snapshots"
    )

    assert response == {
        "files": [{"path": "/snapshots/a.jpg"}, {"path": "/snapshots/sub/b.jpg"}]
    }
    assert webdav_client.mkdir.call_args_list == [
        call("/snapshots", parents=True, exist_ok=True),
        call("/snapshots/sub", parents=True, exist_ok=True),
    ]
    assert uploaded == {"/snapshots/a.jpg": b"a", "/snapshots/sub/b.jpg": b"b"}


@pytest.mark.parametrize(
    ("filename", "destination_folder", "translation_key"),
    [
        pytest.param(
            "/etc/passwd", "backups", "no_access_to_path", id="path_not_allowed"
        ),
        pytest.param(
            "/etc/*.conf", "backups", "no_access_to_path", id="glob_not_allowed"
        ),
        pytest.param(
            "{tmp}/missing.jpg", "backups", "filenames_do_not_exist", id="missing"
        ),
        pytest.param("{tmp}/*.png", "backups", "no_files_match_pattern", id="no_match"),
        pytest.param(
            "{tmp}/snapshot.jpg",
            "../outside",
            "invalid_destination_path",
            id="path_traversal",
        ),
    ],
)
async def test_upload_validation_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    filename: str,
    destination_folder: str,
    translation_key: str,
) -> None:
    """Test invalid input is rejected before anything is uploaded."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_upload(
            hass,
            mock_config_entry,
            filename.format(tmp=tmp_path),
            destination_folder,
        )

    assert exc_info.value.translation_key == translation_key
    webdav_client.write.assert_not_called()


@pytest.mark.parametrize(
    ("method", "error", "translation_key"),
    [
        pytest.param(
            "mkdir",
            AccessDeniedError("/photos"),
            "create_folder_error",
            id="mkdir_error",
        ),
        pytest.param("mkdir", TimeoutError, "create_folder_error", id="mkdir_timeout"),
        pytest.param(
            "write",
            ConnectionExceptionError(ConnectionError("Connection refused")),
            "upload_error",
            id="write_error",
        ),
        pytest.param("write", WebDavError, "upload_error", id="write_webdav_error"),
    ],
)
async def test_upload_server_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    method: str,
    error: Exception,
    translation_key: str,
) -> None:
    """Test errors from the WebDAV server are raised as translated errors."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)
    getattr(webdav_client, method).side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_upload(
            hass, mock_config_entry, str(tmp_path / "snapshot.jpg"), "photos"
        )

    assert exc_info.value.translation_key == translation_key


@pytest.mark.parametrize("method", ["mkdir", "write"])
async def test_upload_unauthorized(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    method: str,
) -> None:
    """Test an authentication error starts a reauth flow."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)
    getattr(webdav_client, method).side_effect = UnauthorizedError("Unauthorized")

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_upload(
            hass, mock_config_entry, str(tmp_path / "snapshot.jpg"), "photos"
        )

    assert exc_info.value.translation_key == "invalid_username_password"
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("webdav_client")
async def test_upload_entry_not_loaded(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test uploading with an unloaded config entry fails."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError):
        await _call_upload(
            hass, mock_config_entry, str(tmp_path / "snapshot.jpg"), "photos"
        )
