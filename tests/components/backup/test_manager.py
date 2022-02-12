"""Tests for the Backup integration."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from awesomeversion import AwesomeVersion
import pytest

from homeassistant.components.backup import BackupManager
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import TEST_BACKUP


async def test_constructor(hass: HomeAssistant) -> None:
    """Test BackupManager constructor."""
    manager = BackupManager(hass)
    assert manager.backup_dir.as_posix() == hass.config.path("backups")


async def test_load_backups(hass: HomeAssistant) -> None:
    """Test loading backups."""
    manager = BackupManager(hass)

    with patch("pathlib.Path.glob", return_value=[Path("abc123.tar")]), patch(
        "tarfile.open", return_value=MagicMock()
    ), patch(
        "json.loads",
        return_value={
            "slug": "abc123",
            "name": "Test",
            "date": "1970-01-01T00:00:00.000Z",
        },
    ), patch(
        "pathlib.Path.stat", return_value=MagicMock(st_size=123)
    ):
        await manager.load_backups()
        assert manager.backups == {TEST_BACKUP.slug: TEST_BACKUP}


async def test_removing_non_existing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing not existing backup."""
    manager = BackupManager(hass)
    assert not manager.backups

    manager.remove_backup("non_existing")
    assert "Removed backup located at" not in caplog.text


async def test_generate_backup_for_non_dev(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)
    with patch("tarfile.open", return_value=MagicMock()) as mocked_tarfile, patch(
        "homeassistant.components.backup.manager.json_util.save_json"
    ) as mocked_json_util, patch(
        "homeassistant.components.backup.manager.HA_VERSION_OBJ",
        AwesomeVersion("2025.1.0"),
    ):
        await manager.generate_backup()

        assert mocked_json_util.call_count == 1
        assert mocked_json_util.call_args[0][1]["homeassistant"] == {
            "version": "2025.1.0"
        }

        assert (
            manager.backup_dir.as_posix()
            in mocked_tarfile.call_args_list[-1][0][0].as_posix()
        )

    assert "Generated new backup with slug " in caplog.text


async def test_generate_backup_for_dev(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)
    with patch("tarfile.open", return_value=MagicMock()), patch(
        "homeassistant.components.backup.manager.json_util.save_json"
    ) as mocked_json_util, patch(
        "homeassistant.components.backup.manager.HA_VERSION_OBJ",
        AwesomeVersion("2025.1.0dev0"),
    ):
        await manager.generate_backup()

        assert mocked_json_util.call_count == 1
        assert mocked_json_util.call_args[0][1]["homeassistant"] == {}

    assert "Generated new backup with slug " in caplog.text


async def test_generate_backup_when_backing_up(hass: HomeAssistant) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)
    manager.backing_up = True
    with pytest.raises(HomeAssistantError, match="Backup in progress"):
        await manager.generate_backup()
