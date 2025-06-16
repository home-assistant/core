"""Test fixtures for the Backup integration."""

from __future__ import annotations

from asyncio import Future
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.backup import DOMAIN
from homeassistant.components.backup.manager import NewBackup, WrittenBackup
from homeassistant.core import HomeAssistant

from .common import TEST_BACKUP_PATH_ABC123, TEST_BACKUP_PATH_DEF456

from tests.common import get_fixture_path


@pytest.fixture(name="instance_id", autouse=True)
def instance_id_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock instance ID."""
    with patch(
        "homeassistant.components.backup.manager.instance_id.async_get",
        return_value="our_uuid",
    ):
        yield


@pytest.fixture(name="mocked_json_bytes")
def mocked_json_bytes_fixture() -> Generator[Mock]:
    """Mock json_bytes."""
    with patch(
        "homeassistant.components.backup.manager.json_bytes",
        return_value=b"{}",  # Empty JSON
    ) as mocked_json_bytes:
        yield mocked_json_bytes


@pytest.fixture(name="mocked_tarfile")
def mocked_tarfile_fixture() -> Generator[Mock]:
    """Mock tarfile."""
    with patch(
        "homeassistant.components.backup.manager.SecureTarFile"
    ) as mocked_tarfile:
        yield mocked_tarfile


@pytest.fixture(name="path_glob")
def path_glob_fixture(hass: HomeAssistant) -> Generator[MagicMock]:
    """Mock path glob."""
    with patch(
        "pathlib.Path.glob",
        return_value=[
            Path(hass.config.path()) / "backups" / TEST_BACKUP_PATH_ABC123,
            Path(hass.config.path()) / "backups" / TEST_BACKUP_PATH_DEF456,
        ],
    ) as path_glob:
        yield path_glob


CONFIG_DIR = {
    "tests/testing_config": [
        Path("test.txt"),
        Path(".DS_Store"),
        Path(".storage"),
        Path("another_subdir"),
        Path("backups"),
        Path("tmp_backups"),
        Path("tts"),
        Path("home-assistant_v2.db"),
    ],
    "/backups": [
        Path("backups/backup.tar"),
        Path("backups/not_backup"),
    ],
    "/another_subdir": [
        Path("another_subdir/.DS_Store"),
        Path("another_subdir/backups"),
        Path("another_subdir/tts"),
    ],
    "another_subdir/backups": [
        Path("another_subdir/backups/backup.tar"),
        Path("another_subdir/backups/not_backup"),
    ],
    "another_subdir/tts": [
        Path("another_subdir/tts/voice.mp3"),
    ],
    "/tmp_backups": [  # noqa: S108
        Path("tmp_backups/forgotten_backup.tar"),
        Path("tmp_backups/not_backup"),
    ],
    "/tts": [
        Path("tts/voice.mp3"),
    ],
}
CONFIG_DIR_DIRS = {
    Path(".storage"),
    Path("another_subdir"),
    Path("another_subdir/backups"),
    Path("another_subdir/tts"),
    Path("backups"),
    Path("tmp_backups"),
    Path("tts"),
}


@pytest.fixture(name="create_backup")
def mock_create_backup() -> Generator[AsyncMock]:
    """Mock manager create backup."""
    mock_written_backup = MagicMock(spec_set=WrittenBackup)
    mock_written_backup.addon_errors = {}
    mock_written_backup.backup.backup_id = "abc123"
    mock_written_backup.backup.protected = False
    mock_written_backup.folder_errors = {}
    mock_written_backup.open_stream = AsyncMock()
    mock_written_backup.release_stream = AsyncMock()
    fut: Future[MagicMock] = Future()
    fut.set_result(mock_written_backup)
    with patch(
        "homeassistant.components.backup.CoreBackupReaderWriter.async_create_backup"
    ) as mock_create_backup:
        mock_create_backup.return_value = (NewBackup(backup_job_id="abc123"), fut)
        yield mock_create_backup


@pytest.fixture(name="mock_backup_generation")
def mock_backup_generation_fixture(
    hass: HomeAssistant, mocked_json_bytes: Mock, mocked_tarfile: Mock
) -> Generator[None]:
    """Mock backup generator."""

    with (
        patch(
            "pathlib.Path.iterdir",
            lambda x: CONFIG_DIR.get(f"{x.parent.name}/{x.name}", []),
        ),
        patch("pathlib.Path.stat", return_value=MagicMock(st_size=123)),
        patch("pathlib.Path.is_file", lambda x: x not in CONFIG_DIR_DIRS),
        patch("pathlib.Path.is_dir", lambda x: x in CONFIG_DIR_DIRS),
        patch(
            "pathlib.Path.exists",
            lambda x: x
            not in (
                Path(hass.config.path("backups")),
                Path(hass.config.path("tmp_backups")),
            ),
        ),
        patch(
            "pathlib.Path.is_symlink",
            lambda _: False,
        ),
        patch(
            "pathlib.Path.mkdir",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.backup.manager.HAVERSION",
            "2025.1.0",
        ),
    ):
        yield


@pytest.fixture
def mock_backups() -> Generator[None]:
    """Fixture to setup test backups."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.backup import backup as core_backup

    class CoreLocalBackupAgent(core_backup.CoreLocalBackupAgent):
        def __init__(self, hass: HomeAssistant) -> None:
            super().__init__(hass)
            self._backup_dir = get_fixture_path("test_backups", DOMAIN)

    with patch.object(core_backup, "CoreLocalBackupAgent", CoreLocalBackupAgent):
        yield
