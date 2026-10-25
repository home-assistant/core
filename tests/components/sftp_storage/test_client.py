"""Test backup paths against an SFTP server with a real filesystem."""

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

from asyncssh import SFTPServer, SSHServer, generate_private_key, listen
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.backup import BackupAgentError, suggested_filename
from homeassistant.components.sftp_storage.client import BackupAgentClient
from homeassistant.core import HomeAssistant

from .conftest import BACKUP_METADATA, TEST_AGENT_BACKUP

pytestmark = pytest.mark.usefixtures("socket_enabled")


class NoAuthSSHServer(SSHServer):
    """Allow local test connections without authentication."""

    def begin_auth(self, username: str) -> bool:
        """Skip authentication for the test server."""
        return False


@pytest.fixture
async def sftp_server(tmp_path: Path) -> AsyncGenerator[int]:
    """Serve the temporary directory as the SFTP filesystem root."""
    async with listen(
        "127.0.0.1",
        0,
        server_factory=NoAuthSSHServer,
        server_host_keys=[generate_private_key("ssh-ed25519")],
        sftp_factory=lambda channel: SFTPServer(channel, chroot=str(tmp_path)),
    ) as server:
        yield server.get_port()


@pytest.mark.parametrize(
    ("backup_location", "directory"),
    [
        pytest.param(".", ".", id="login-directory"),
        pytest.param("backups", "backups", id="relative-directory"),
        pytest.param(
            "nested/backups", "nested/backups", id="nested-relative-directory"
        ),
        pytest.param("/backups", "backups", id="absolute-directory"),
    ],
)
async def test_backup_roundtrip(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sftp_server: int,
    tmp_path: Path,
    backup_location: str,
    directory: str,
) -> None:
    """Upload, list, download and delete backups without repeating the directory."""
    backup_dir = tmp_path / directory
    backup_dir.mkdir(parents=True, exist_ok=True)
    config_entry.runtime_data = replace(
        config_entry.runtime_data, port=sftp_server, backup_location=backup_location
    )

    async def stream() -> AsyncIterator[bytes]:
        yield b"backup data"

    async with BackupAgentClient(config_entry, hass) as client:
        await client.async_upload_backup(stream(), TEST_AGENT_BACKUP, Mock())

    filename = suggested_filename(TEST_AGENT_BACKUP)
    archive = backup_dir / filename
    metadata_file = backup_dir / f".{TEST_AGENT_BACKUP.backup_id}.metadata.json"
    metadata = json.loads(metadata_file.read_text())
    assert metadata["file_path"] == filename
    assert archive.read_bytes() == b"backup data"

    async with BackupAgentClient(config_entry, hass) as client:
        assert await client.async_list_backups() == [TEST_AGENT_BACKUP]
        assert await client.async_list_backups() == [TEST_AGENT_BACKUP]
        reader = await client.iter_file(TEST_AGENT_BACKUP.backup_id)
        assert b"".join([chunk async for chunk in reader]) == b"backup data"

    async with BackupAgentClient(config_entry, hass) as client:
        await client.async_delete_backup(TEST_AGENT_BACKUP.backup_id)

    assert not archive.exists()
    assert not metadata_file.exists()
    assert config_entry.runtime_data.backup_location == backup_location


@pytest.mark.parametrize(
    ("backup_location", "directory", "other_directory"),
    [
        pytest.param(
            "backup_location",
            "backup_location",
            "unrelated",
            id="relative-same-directory",
        ),
        pytest.param(
            "/backup_location",
            "backup_location",
            "unrelated",
            id="absolute-same-directory",
        ),
        pytest.param("backups", "backups", "backups", id="relative-other-directory"),
        pytest.param("/backups", "backups", "backups", id="absolute-other-directory"),
    ],
)
async def test_legacy_absolute_metadata(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sftp_server: int,
    tmp_path: Path,
    backup_location: str,
    directory: str,
    other_directory: str,
) -> None:
    """Honor the exact legacy archive path even when a same-named file exists."""
    backup_dir = tmp_path / directory
    backup_dir.mkdir()
    legacy_dir = tmp_path / "backup_location"
    legacy_dir.mkdir(exist_ok=True)
    archive = legacy_dir / "backup.tar"
    archive.write_bytes(b"legacy backup")
    other_dir = tmp_path / other_directory
    other_dir.mkdir(exist_ok=True)
    other_archive = other_dir / "backup.tar"
    other_archive.write_bytes(b"different backup")
    metadata_file = backup_dir / f".{TEST_AGENT_BACKUP.backup_id}.metadata.json"
    original_metadata = json.dumps(BACKUP_METADATA)
    metadata_file.write_text(original_metadata)
    config_entry.runtime_data = replace(
        config_entry.runtime_data, port=sftp_server, backup_location=backup_location
    )

    async with BackupAgentClient(config_entry, hass) as client:
        assert await client.async_list_backups() == [TEST_AGENT_BACKUP]
        reader = await client.iter_file(TEST_AGENT_BACKUP.backup_id)
        assert b"".join([chunk async for chunk in reader]) == b"legacy backup"
        assert metadata_file.read_text() == original_metadata
        await client.async_delete_backup(TEST_AGENT_BACKUP.backup_id)

    assert not archive.exists()
    assert not metadata_file.exists()
    assert other_archive.read_bytes() == b"different backup"


async def test_missing_legacy_archive_does_not_fall_back(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sftp_server: int,
    tmp_path: Path,
) -> None:
    """Do not substitute a different archive for a missing absolute path."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "backup.tar").write_bytes(b"different backup")
    metadata_file = backup_dir / f".{TEST_AGENT_BACKUP.backup_id}.metadata.json"
    metadata_file.write_text(json.dumps(BACKUP_METADATA))
    config_entry.runtime_data = replace(
        config_entry.runtime_data, port=sftp_server, backup_location="backups"
    )

    async with BackupAgentClient(config_entry, hass) as client:
        with pytest.raises(FileNotFoundError, match="Backup archive not found"):
            await client.iter_file(TEST_AGENT_BACKUP.backup_id)

    assert metadata_file.exists()
    assert (backup_dir / "backup.tar").read_bytes() == b"different backup"


@pytest.mark.parametrize("backup_name", ["/outside", "../outside"])
async def test_upload_rejects_non_filename(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    sftp_server: int,
    tmp_path: Path,
    backup_name: str,
) -> None:
    """New metadata must reference a filename within the backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    config_entry.runtime_data = replace(
        config_entry.runtime_data, port=sftp_server, backup_location="backups"
    )

    async def stream() -> AsyncIterator[bytes]:
        yield b"backup data"

    async with BackupAgentClient(config_entry, hass) as client:
        with pytest.raises(BackupAgentError, match="Invalid backup filename"):
            await client.async_upload_backup(
                stream(), replace(TEST_AGENT_BACKUP, name=backup_name), Mock()
            )

    assert list(backup_dir.iterdir()) == []
