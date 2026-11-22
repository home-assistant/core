"""Tests for WebDAV services."""

import asyncio
from collections.abc import AsyncIterable
import errno
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
from pytest_homeassistant.common import MockConfigEntry, MockUser

from homeassistant.components.webdav.const import (
    DOMAIN,
    WebDavService,
    WebDavServiceArgument,
)
from homeassistant.components.webdav.services import UPLOAD_TIMEOUT
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CommonServiceArgument
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)

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
    context: Context | None = None,
) -> Any:
    return await hass.services.async_call(
        DOMAIN,
        WebDavService.UPLOAD,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: entry.entry_id,
            WebDavServiceArgument.FILENAME: filename,
            WebDavServiceArgument.DESTINATION_FOLDER: destination_folder,
        },
        blocking=True,
        return_response=True,
        context=context,
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
        WebDavService.UPLOAD,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            WebDavServiceArgument.FILENAME: str(tmp_path / "snapshot.jpg"),
            WebDavServiceArgument.DESTINATION_FOLDER: "/",
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
    ("filenames", "destination_folder", "translation_key"),
    [
        pytest.param(
            ["/etc/passwd"], "backups", "no_access_to_path", id="path_not_allowed"
        ),
        pytest.param(
            ["/etc/*.conf"], "backups", "no_access_to_path", id="glob_not_allowed"
        ),
        pytest.param(
            ["{tmp}/missing.jpg"], "backups", "filenames_do_not_exist", id="missing"
        ),
        pytest.param(
            ["{tmp}/*.png"], "backups", "no_files_match_pattern", id="no_match"
        ),
        pytest.param(
            ["{tmp}/snapshot.jpg"],
            "../outside",
            "invalid_destination_path",
            id="path_traversal",
        ),
        pytest.param(
            ["{tmp}/a/snapshot.jpg", "{tmp}/b/snapshot.jpg"],
            "backups",
            "duplicate_destination_path",
            id="duplicate_destination",
        ),
    ],
)
async def test_upload_validation_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
    filenames: list[str],
    destination_folder: str,
    translation_key: str,
) -> None:
    """Test invalid input is rejected before anything is uploaded."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    for folder in ("a", "b"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)
    webdav_client.mkdir.reset_mock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call_upload(
            hass,
            mock_config_entry,
            [filename.format(tmp=tmp_path) for filename in filenames],
            destination_folder,
        )

    assert exc_info.value.translation_key == translation_key
    webdav_client.mkdir.assert_not_called()
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


async def test_upload_requires_admin(
    hass: HomeAssistant,
    tmp_path: Path,
    hass_read_only_user: MockUser,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
) -> None:
    """Test uploading requires an admin user."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(Unauthorized):
        await _call_upload(
            hass,
            mock_config_entry,
            str(tmp_path / "snapshot.jpg"),
            "photos",
            Context(user_id=hass_read_only_user.id),
        )

    webdav_client.write.assert_not_called()


async def test_upload_read_error(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
) -> None:
    """Test a local read error is raised as a translated error."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)

    with (
        patch.object(Path, "open", side_effect=PermissionError(errno.EACCES, "Denied")),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _call_upload(
            hass, mock_config_entry, str(tmp_path / "snapshot.jpg"), "photos"
        )

    assert exc_info.value.translation_key == "os_read_permission_denied"
    webdav_client.write.assert_not_called()


async def test_upload_file_grows_after_open(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
) -> None:
    """Test the body matches Content-Length when the file grows during upload."""
    path = tmp_path / "snapshot.jpg"
    path.write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)
    uploaded: dict[str, bytes] = {}

    async def _write(
        remote: str, data: AsyncIterable[bytes], content_length: int, **kwargs: Any
    ) -> None:
        with path.open("ab") as file:
            file.write(b" more data")
        uploaded[remote] = b"".join([chunk async for chunk in data])
        assert len(uploaded[remote]) == content_length

    webdav_client.write.side_effect = _write

    await _call_upload(hass, mock_config_entry, str(path), "photos")

    assert uploaded == {"/photos/snapshot.jpg": b"data"}


async def test_upload_failure_cancels_remaining(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
) -> None:
    """Test a failed upload cancels the uploads still running."""
    (tmp_path / "a.jpg").write_bytes(b"a")
    (tmp_path / "b.jpg").write_bytes(b"b")
    await setup_integration(hass, mock_config_entry)
    started = asyncio.Event()
    cancelled: list[str] = []

    async def _write(path: str, data: AsyncIterable[bytes], **kwargs: Any) -> None:
        if path == "/photos/b.jpg":
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(path)
                raise
        await started.wait()
        raise WebDavError

    webdav_client.write.side_effect = _write

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call_upload(
            hass,
            mock_config_entry,
            [str(tmp_path / "a.jpg"), str(tmp_path / "b.jpg")],
            "photos",
        )

    assert exc_info.value.translation_key == "upload_error"
    assert cancelled == ["/photos/b.jpg"]


async def test_upload_unexpected_error(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_config_entry: MockConfigEntry,
    webdav_client: AsyncMock,
) -> None:
    """Test an unexpected upload error is not translated."""
    (tmp_path / "snapshot.jpg").write_bytes(b"data")
    await setup_integration(hass, mock_config_entry)
    webdav_client.write.side_effect = ValueError("boom")

    with pytest.raises(ExceptionGroup) as exc_info:
        await _call_upload(
            hass, mock_config_entry, str(tmp_path / "snapshot.jpg"), "photos"
        )

    assert exc_info.group_contains(ValueError)
