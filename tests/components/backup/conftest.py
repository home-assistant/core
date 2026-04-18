"""Test fixtures for the Backup integration."""

from __future__ import annotations

from asyncio import Future
from collections.abc import Generator
from pathlib import Path
import shutil
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.backup import DOMAIN
from homeassistant.components.backup.manager import NewBackup, WrittenBackup
from homeassistant.core import HomeAssistant

from tests.common import get_fixture_path


@pytest.fixture
def available_backups() -> list[Path]:
    """Fixture to provide available backup files."""
    return []


@pytest.fixture
def hass_config_dir(tmp_path: Path, available_backups: list[Path]) -> str:
    """Fixture to create a temporary config directory, populated with test files."""
    shutil.copytree(
        get_fixture_path("config_dir_contents", DOMAIN),
        tmp_path,
        symlinks=True,
        dirs_exist_ok=True,
    )
    for backup in available_backups:
        (get_fixture_path("test_backups", DOMAIN) / backup).copy_into(
            tmp_path / "backups"
        )
    return tmp_path.as_posix()


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


@pytest.fixture(name="mock_ha_version")
def mock_ha_version_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock HA version.

    The HA version is included in backup metadata. We mock it for the benefit
    of tests that check the exact content of the metadata.
    """

    with patch("homeassistant.components.backup.manager.HAVERSION", "2025.1.0"):
        yield


@pytest.fixture
def mock_backups() -> Generator[None]:
    """Fixture to setup test backups."""
    from homeassistant.components.backup import backup as core_backup  # noqa: PLC0415

    class CoreLocalBackupAgent(core_backup.CoreLocalBackupAgent):
        def __init__(self, hass: HomeAssistant) -> None:
            super().__init__(hass)
            self._backup_dir = get_fixture_path("test_backups", DOMAIN)

    with patch.object(core_backup, "CoreLocalBackupAgent", CoreLocalBackupAgent):
        yield
