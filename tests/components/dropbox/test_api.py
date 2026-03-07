"""Test the DropboxClient."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from python_dropbox_api import DropboxAuthException, DropboxUnknownException

from homeassistant.components.backup import AgentBackup, BackupNotFound
from homeassistant.components.dropbox.api import (
    DropboxClient,
    _async_string_iterator,
    suggested_filenames,
)

TEST_BACKUP = AgentBackup(
    addons=[],
    backup_id="test-backup-id",
    database_included=True,
    date="2025-01-01T00:00:00.000Z",
    extra_metadata={},
    folders=[],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test backup",
    protected=False,
    size=1024,
)


@pytest.fixture
def mock_api() -> MagicMock:
    """Return a mocked DropboxAPIClient."""
    return MagicMock()


@pytest.fixture
def client(mock_api: MagicMock) -> DropboxClient:
    """Return a DropboxClient with a mocked API."""
    auth = MagicMock()
    with patch(
        "homeassistant.components.dropbox.api.DropboxAPIClient", return_value=mock_api
    ):
        return DropboxClient(auth)


def test_suggested_filenames() -> None:
    """Test generating suggested filenames for backup and metadata."""
    tar_name, metadata_name = suggested_filenames(TEST_BACKUP)

    assert tar_name.endswith(".tar")
    assert metadata_name.endswith(".metadata.json")
    assert tar_name.removesuffix(".tar") == metadata_name.removesuffix(".metadata.json")


async def test_async_string_iterator() -> None:
    """Test the async string iterator yields encoded bytes."""
    chunks = [chunk async for chunk in _async_string_iterator("hello")]

    assert chunks == [b"hello"]


async def test_get_account_info(client: DropboxClient, mock_api: MagicMock) -> None:
    """Test getting account information."""
    expected = SimpleNamespace(account_id="123", email="test@example.com")
    mock_api.get_account_info = AsyncMock(return_value=expected)

    result = await client.async_get_account_info()

    assert result == expected
    mock_api.get_account_info.assert_awaited_once()


async def _mock_download_stream(content: bytes) -> AsyncIterator[bytes]:
    """Create a mock download stream."""
    yield content


async def test_list_backups(client: DropboxClient, mock_api: MagicMock) -> None:
    """Test listing backups with matching tar and metadata files."""
    tar_name, metadata_name = suggested_filenames(TEST_BACKUP)

    mock_api.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name=tar_name),
            SimpleNamespace(name=metadata_name),
        ]
    )
    mock_api.download_file = MagicMock(
        return_value=_mock_download_stream(json.dumps(TEST_BACKUP.as_dict()).encode())
    )

    backups = await client.async_list_backups()

    assert len(backups) == 1
    assert backups[0].backup_id == TEST_BACKUP.backup_id
    mock_api.list_folder.assert_awaited_once_with("")


async def test_list_backups_metadata_without_tar(
    client: DropboxClient, mock_api: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that orphaned metadata files are skipped with a warning."""
    mock_api.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name="orphan.metadata.json"),
        ]
    )

    backups = await client.async_list_backups()

    assert len(backups) == 0
    assert "without matching backup file" in caplog.text


async def test_upload_backup(client: DropboxClient, mock_api: MagicMock) -> None:
    """Test uploading a backup and its metadata."""
    mock_api.upload_file = AsyncMock()

    async def _stream() -> AsyncIterator[bytes]:
        yield b"backup data"

    async def mock_open_stream() -> AsyncIterator[bytes]:
        return _stream()

    await client.async_upload_backup(mock_open_stream, TEST_BACKUP)

    assert mock_api.upload_file.await_count == 2


async def test_upload_backup_metadata_fails_cleans_up(
    client: DropboxClient, mock_api: MagicMock
) -> None:
    """Test that backup file is deleted when metadata upload fails."""
    call_count = 0

    async def upload_side_effect(path: str, stream: AsyncIterator[bytes]) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise DropboxUnknownException("metadata upload failed")

    mock_api.upload_file = AsyncMock(side_effect=upload_side_effect)
    mock_api.delete_file = AsyncMock()

    async def _stream() -> AsyncIterator[bytes]:
        yield b"backup data"

    async def mock_open_stream() -> AsyncIterator[bytes]:
        return _stream()

    with pytest.raises(DropboxUnknownException):
        await client.async_upload_backup(mock_open_stream, TEST_BACKUP)

    mock_api.delete_file.assert_awaited_once()


async def test_upload_backup_metadata_auth_fails_cleans_up(
    client: DropboxClient, mock_api: MagicMock
) -> None:
    """Test that backup file is deleted when metadata upload fails with auth error."""
    call_count = 0

    async def upload_side_effect(path: str, stream: AsyncIterator[bytes]) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise DropboxAuthException("auth failed")

    mock_api.upload_file = AsyncMock(side_effect=upload_side_effect)
    mock_api.delete_file = AsyncMock()

    async def _stream() -> AsyncIterator[bytes]:
        yield b"backup data"

    async def mock_open_stream() -> AsyncIterator[bytes]:
        return _stream()

    with pytest.raises(DropboxAuthException):
        await client.async_upload_backup(mock_open_stream, TEST_BACKUP)

    mock_api.delete_file.assert_awaited_once()


async def test_download_backup(client: DropboxClient, mock_api: MagicMock) -> None:
    """Test downloading a backup by ID."""
    tar_name, metadata_name = suggested_filenames(TEST_BACKUP)

    mock_api.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name=tar_name),
            SimpleNamespace(name=metadata_name),
        ]
    )
    mock_api.download_file = MagicMock(
        return_value=_mock_download_stream(json.dumps(TEST_BACKUP.as_dict()).encode())
    )

    result = await client.async_download_backup(TEST_BACKUP.backup_id)

    assert result is not None


async def test_download_backup_not_found(
    client: DropboxClient, mock_api: MagicMock
) -> None:
    """Test downloading a backup that does not exist."""
    mock_api.list_folder = AsyncMock(return_value=[])

    with pytest.raises(BackupNotFound, match="not found"):
        await client.async_download_backup("nonexistent-id")


async def test_delete_backup(client: DropboxClient, mock_api: MagicMock) -> None:
    """Test deleting a backup and its metadata."""
    tar_name, metadata_name = suggested_filenames(TEST_BACKUP)

    mock_api.list_folder = AsyncMock(
        return_value=[
            SimpleNamespace(name=tar_name),
            SimpleNamespace(name=metadata_name),
        ]
    )
    mock_api.download_file = MagicMock(
        return_value=_mock_download_stream(json.dumps(TEST_BACKUP.as_dict()).encode())
    )
    mock_api.delete_file = AsyncMock()

    await client.async_delete_backup(TEST_BACKUP.backup_id)

    assert mock_api.delete_file.await_count == 2


async def test_delete_backup_not_found(
    client: DropboxClient, mock_api: MagicMock
) -> None:
    """Test deleting a backup that does not exist."""
    mock_api.list_folder = AsyncMock(return_value=[])

    with pytest.raises(BackupNotFound, match="not found"):
        await client.async_delete_backup("nonexistent-id")
