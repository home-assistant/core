"""Test client for SFTP Backup Location component."""

from collections.abc import Callable
import json
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from homeassistant.components.backup import AgentBackup

# Import the classes and functions under test.
from homeassistant.components.backup_sftp.client import (
    AsyncFileIterator,
    BackupAgentClient,
    BackupMetadata,
)
from homeassistant.core import HomeAssistant, HomeAssistantError

from . import setup_backup_integration  # noqa: F401

from tests.common import MockConfigEntry

BACKUP_METADATA = {
    "file_path": "backup_location/backup.tar",
    "metadata": {
        "addons": [],
        "backup_id": "abcd1234",
        "date": "2025-02-26T23:07:03.263827+01:00",
        "database_included": True,
        "extra_metadata": {
            "instance_id": 1,
            "with_automatic_settings": False,
            "supervisor.backup_request_date": "2025-02-26T23:07:03.263827+01:00",
        },
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2025.2.5",
        "name": "Backup 2025.2.5",
        "protected": True,
        "size": 1234,
    },
}


class Mocks:
    """Store nested mock objects for easier edit."""

    def __init__(self, connect: AsyncMock) -> None:
        """Initialize `Mocks` object."""
        self.connect: AsyncMock = connect

    def __call__(self) -> AsyncMock:
        """Return connect mocked object on instance call."""
        return self.connect

    @property
    def start_sftp_client(self) -> AsyncMock:
        """Read value of `start_sftp_client` mock object."""
        return self.connect.return_value.start_sftp_client

    @start_sftp_client.setter
    def start_sftp_client(self, val: AsyncMock | MagicMock):
        self.connect.return_value.start_sftp_client = val

    @property
    def open(self) -> MagicMock:
        """Read value of `open` mock object."""
        return self.connect.return_value.start_sftp_client.return_value.open

    @open.setter
    def open(self, val: AsyncMock | MagicMock):
        self.connect.return_value.start_sftp_client.return_value.open = val

    @property
    def read(self) -> AsyncMock:
        """Read value of `read` mock object."""
        return self.connect.return_value.start_sftp_client.return_value.open.read

    @read.setter
    def read(self, val: AsyncMock | MagicMock):
        self.connect.return_value.start_sftp_client.return_value.open.read = val

    @property
    def write(self) -> AsyncMock:
        """Read value of `write` mock object."""
        return self.connect.return_value.start_sftp_client.return_value.open.write

    @write.setter
    def write(self, val: AsyncMock | MagicMock):
        self.connect.return_value.start_sftp_client.return_value.open.write = val

    @property
    def exists(self) -> AsyncMock:
        """Read value of `exists` mock object."""
        return self.connect.return_value.start_sftp_client.return_value.exists

    @exists.setter
    def exists(self, val: AsyncMock | MagicMock):
        self.connect.return_value.start_sftp_client.return_value.exists = val

    @property
    def unlink(self) -> AsyncMock:
        """Read value of `unlink` mock object."""
        return self.connect.return_value.start_sftp_client.return_value.unlink

    @unlink.setter
    def unlink(self, val: AsyncMock | MagicMock):
        self.connect.return_value.start_sftp_client.return_value.unlink = val


@pytest.fixture
async def mock_connect(async_cm_mock_generator: Callable[..., MagicMock]) -> Mocks:
    """Mock return value for `asyncssh.connect`."""
    connect = AsyncMock()

    mock_open_cm = async_cm_mock_generator()
    mock_open_cm.read = AsyncMock(return_value=json.dumps(BACKUP_METADATA))
    mock_open_cm.write = AsyncMock()

    start_sftp_client = AsyncMock()
    start_sftp_client.return_value.exists = AsyncMock(return_value=True)
    start_sftp_client.return_value.listdir = AsyncMock(
        return_value=["slug_hass_backup_metadata.json"]
    )
    start_sftp_client.return_value.open = mock_open_cm

    connect.return_value.__aenter__.return_value = connect
    connect.return_value.start_sftp_client = start_sftp_client
    return Mocks(connect=connect)


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_client_aenter_fail_oserror(
    config_entry: MockConfigEntry, hass: HomeAssistant, mock_connect: Mocks
) -> None:
    """Test exceptions in `__aenter__` method of `BackupAgentClient` class.

    Should raise:
    - `HomeAssistantError` on any connection error attempts - that's when connection fails.
    - `RuntimeError` on SFTP Connection error.
    """

    mock_connect.connect.side_effect = OSError("Error message")
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
        pytest.raises(HomeAssistantError),
    ):
        async with BackupAgentClient(config_entry, hass):
            pass

    mock_connect.connect.side_effect = None
    mock_connect.start_sftp_client = AsyncMock(
        side_effect=asyncssh.SFTPNoSuchFile("Error message")
    )
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
        pytest.raises(RuntimeError) as exc,
    ):
        async with BackupAgentClient(config_entry, hass):
            pass

    assert "Failed to create SFTP client." in str(exc)


async def test_client_not_initialized(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test `_initialized` method of `BackupAgentClient`.

    Make sure exceptions are raised when instance is not initialized
    or when wrong file path is provided.
    """

    client = BackupAgentClient(config_entry, hass)
    with pytest.raises(RuntimeError) as exc:
        await client._initialized()
    assert "Connection is not initialized" in str(exc.value)

    client._ssh = True
    client.sftp = True
    with pytest.raises(RuntimeError) as exc:
        await client._initialized("false_file")
    assert "Attempted to access file outside of configured backup location" in str(
        exc.value
    )


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_async_list_backups(
    config_entry: MockConfigEntry, hass: HomeAssistant, mock_connect: Mocks
) -> None:
    """Test `async_list_backups` method of `BackupAgentClient` class."""

    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            backups = await client.async_list_backups()
            assert len(backups) > 0 and isinstance(backups[0], AgentBackup)

    mock_connect.read = AsyncMock(side_effect=RuntimeError("Error message"))
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            backups = await client.async_list_backups()
            assert backups == []


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_async_list_backups_err(
    config_entry: MockConfigEntry,
    hass: HomeAssistant,
    mock_connect: Mocks,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test `async_list_backups` method of `BackupAgentClient` class when error during metadata load occurs."""

    mock_connect.read = AsyncMock(side_effect=RuntimeError("Error message"))

    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            backups = await client.async_list_backups()
            assert backups == []
    assert "Failed to load backup metadata from file" in caplog.text


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_load_metadata(
    config_entry: MockConfigEntry, hass: HomeAssistant, mock_connect: Mocks
) -> None:
    """Test `_load_metadata` method of `BackupAgentClient` class."""

    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            backup = await client._load_metadata(
                AgentBackup(**BACKUP_METADATA["metadata"])
            )
            assert isinstance(backup, BackupMetadata)

    # Test assertion error
    mock_connect.exists = AsyncMock(return_value=False)
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            with pytest.raises(AssertionError) as exc:
                await client._load_metadata(AgentBackup(**BACKUP_METADATA["metadata"]))
    assert "Metadata file not found at remote location" in str(exc.value)
    mock_connect.exists.assert_called_with(
        f"backup_location/.{backup.metadata['backup_id']}_hass_backup_metadata.json"
    )


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_async_delete_backup(
    config_entry: MockConfigEntry, hass: HomeAssistant, mock_connect: Mocks
) -> None:
    """Test `async_delete_backup` method of `BackupAgentClient` class."""

    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            await client.async_delete_backup(AgentBackup(**BACKUP_METADATA["metadata"]))
    assert mock_connect.unlink.call_count == 2

    mock_connect.exists = AsyncMock(return_value=False)
    mock_load_metadata = AsyncMock(
        return_value=BackupMetadata(**BACKUP_METADATA, metadata_file="metadata")
    )
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
        patch(
            "homeassistant.components.backup_sftp.client.BackupAgentClient._load_metadata",
            mock_load_metadata,
        ),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            with pytest.raises(AssertionError) as exc:
                await client.async_delete_backup(
                    AgentBackup(**BACKUP_METADATA["metadata"])
                )
    assert "does not exist" in str(exc.value)


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_async_upload_backup(
    config_entry: MockConfigEntry,
    hass: HomeAssistant,
    mock_connect: Mocks,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test `async_upload_backup` method of `BackupAgentClient` class."""

    mock_iterator = MagicMock()
    mock_iterator.__aiter__.return_value = [b"content", b""]
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            await client.async_upload_backup(
                mock_iterator, AgentBackup(**BACKUP_METADATA["metadata"])
            )
    assert mock_connect.open.call_count == 2
    # mock_iterator returns 2 items, so write will be called 3 times:
    # 2 - during backup file write,
    # 1 - during metadata write.
    assert mock_connect.write.call_count == 3
    assert "Writing backup metadata" in caplog.text


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
async def test_iter_file(
    config_entry: MockConfigEntry, hass: HomeAssistant, mock_connect: Mocks
) -> None:
    """Test `iter_file` method of `BackupAgentClient` class."""

    mock_connect.exists.return_value = False
    mock_load_metadata = AsyncMock(
        return_value=BackupMetadata(**BACKUP_METADATA, metadata_file="metadata")
    )
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
        patch(
            "homeassistant.components.backup_sftp.client.BackupAgentClient._load_metadata",
            mock_load_metadata,
        ),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            with pytest.raises(FileNotFoundError) as exc:
                await client.iter_file(AgentBackup(**BACKUP_METADATA["metadata"]))
            assert "Backup archive not found on remote location" in str(exc.value)

    mock_connect.exists.return_value = True
    with (
        patch("homeassistant.components.backup_sftp.client.connect", mock_connect()),
        patch(
            "homeassistant.components.backup_sftp.client.BackupAgentClient._load_metadata",
            mock_load_metadata,
        ),
    ):
        async with BackupAgentClient(config_entry, hass) as client:
            res = await client.iter_file(AgentBackup(**BACKUP_METADATA["metadata"]))

        assert isinstance(res, AsyncFileIterator)

        mock_open = AsyncMock()
        mock_open.return_value.read = AsyncMock(side_effect=[b"content", b""])
        mock_connect.open = mock_open
        async for b in res:
            assert b == b"content"

    assert mock_open.return_value.read.call_count == 2
