"""Tests for the Backup integration."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.backup import BackupManager
from homeassistant.components.backup.manager import BackupPlatformProtocol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import TEST_BACKUP

from tests.common import MockPlatform, mock_platform


async def _mock_backup_generation(manager: BackupManager):
    """Mock backup generator."""

    def _mock_iterdir(path: Path) -> list[Path]:
        if not path.name.endswith("testing_config"):
            return []
        return [
            Path("test.txt"),
            Path(".DS_Store"),
            Path(".storage"),
        ]

    with patch("tarfile.open", MagicMock()) as mocked_tarfile, patch(
        "pathlib.Path.iterdir", _mock_iterdir
    ), patch("pathlib.Path.stat", MagicMock(st_size=123)), patch(
        "pathlib.Path.is_file", lambda x: x.name != ".storage"
    ), patch(
        "pathlib.Path.is_dir",
        lambda x: x.name == ".storage",
    ), patch(
        "pathlib.Path.exists",
        lambda x: x != manager.backup_dir,
    ), patch(
        "pathlib.Path.is_symlink",
        lambda _: False,
    ), patch(
        "pathlib.Path.mkdir",
        MagicMock(),
    ), patch(
        "homeassistant.components.backup.manager.json_util.save_json"
    ) as mocked_json_util, patch(
        "homeassistant.components.backup.manager.HAVERSION",
        "2025.1.0",
    ):
        await manager.generate_backup()

        assert mocked_json_util.call_count == 1
        assert mocked_json_util.call_args[0][1]["homeassistant"] == {
            "version": "2025.1.0"
        }

        assert (
            manager.backup_dir.as_posix()
            in mocked_tarfile.call_args_list[0].kwargs["name"]
        )


async def _setup_mock_domain(
    hass: HomeAssistant,
    platform: BackupPlatformProtocol | None = None,
) -> None:
    """Set up a mock domain."""
    mock_platform(hass, "some_domain.backup", platform or MockPlatform())
    assert await async_setup_component(hass, "some_domain", {})


async def test_constructor(hass: HomeAssistant) -> None:
    """Test BackupManager constructor."""
    manager = BackupManager(hass)
    assert manager.backup_dir.as_posix() == hass.config.path("backups")


async def test_load_backups(hass: HomeAssistant) -> None:
    """Test loading backups."""
    manager = BackupManager(hass)
    with patch("pathlib.Path.glob", return_value=[TEST_BACKUP.path]), patch(
        "tarfile.open", return_value=MagicMock()
    ), patch(
        "json.loads",
        return_value={
            "slug": TEST_BACKUP.slug,
            "name": TEST_BACKUP.name,
            "date": TEST_BACKUP.date,
        },
    ), patch(
        "pathlib.Path.stat", return_value=MagicMock(st_size=TEST_BACKUP.size)
    ):
        await manager.load_backups()
    backups = await manager.get_backups()
    assert backups == {TEST_BACKUP.slug: TEST_BACKUP}


async def test_load_backups_with_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backups with exception."""
    manager = BackupManager(hass)
    with patch("pathlib.Path.glob", return_value=[TEST_BACKUP.path]), patch(
        "tarfile.open", side_effect=OSError("Test ecxeption")
    ):
        await manager.load_backups()
    backups = await manager.get_backups()
    assert f"Unable to read backup {TEST_BACKUP.path}: Test ecxeption" in caplog.text
    assert backups == {}


async def test_removing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing backup."""
    manager = BackupManager(hass)
    manager.backups = {TEST_BACKUP.slug: TEST_BACKUP}
    manager.loaded_backups = True

    with patch("pathlib.Path.exists", return_value=True):
        await manager.remove_backup(TEST_BACKUP.slug)
    assert "Removed backup located at" in caplog.text


async def test_removing_non_existing_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing not existing backup."""
    manager = BackupManager(hass)

    await manager.remove_backup("non_existing")
    assert "Removed backup located at" not in caplog.text


async def test_getting_backup_that_does_not_exist(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
):
    """Test getting backup that does not exist."""
    manager = BackupManager(hass)
    manager.backups = {TEST_BACKUP.slug: TEST_BACKUP}
    manager.loaded_backups = True

    with patch("pathlib.Path.exists", return_value=False):
        backup = await manager.get_backup(TEST_BACKUP.slug)
        assert backup is None

        assert (
            f"Removing tracked backup ({TEST_BACKUP.slug}) that "
            f"does not exists on the expected path {TEST_BACKUP.path}" in caplog.text
        )


async def test_generate_backup_when_backing_up(hass: HomeAssistant) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)
    manager.backing_up = True
    with pytest.raises(HomeAssistantError, match="Backup already in progress"):
        await manager.generate_backup()


async def test_generate_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test generate backup."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    await _mock_backup_generation(manager)

    assert "Generated new backup with slug " in caplog.text
    assert "Creating backup directory" in caplog.text
    assert "Loaded 0 platforms" in caplog.text


async def test_loading_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=AsyncMock(),
        ),
    )
    await manager.load_platforms()

    assert manager.loaded_platforms
    assert len(manager.platforms) == 1

    assert "Loaded 1 platforms" in caplog.text


async def test_not_loading_bad_platforms(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading backup platforms."""
    manager = BackupManager(hass)

    assert not manager.loaded_platforms
    assert not manager.platforms

    await _setup_mock_domain(hass)
    await manager.load_platforms()

    assert manager.loaded_platforms
    assert len(manager.platforms) == 0

    assert "Loaded 0 platforms" in caplog.text
    assert (
        "some_domain does not implement required functions for the backup platform"
        in caplog.text
    )


async def test_exception_plaform_pre(hass: HomeAssistant) -> None:
    """Test exception in pre step."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=_mock_step,
            async_post_backup=AsyncMock(),
        ),
    )

    with pytest.raises(HomeAssistantError):
        await _mock_backup_generation(manager)


async def test_exception_plaform_post(hass: HomeAssistant) -> None:
    """Test exception in post step."""
    manager = BackupManager(hass)
    manager.loaded_backups = True

    async def _mock_step(hass: HomeAssistant) -> None:
        raise HomeAssistantError("Test exception")

    await _setup_mock_domain(
        hass,
        Mock(
            async_pre_backup=AsyncMock(),
            async_post_backup=_mock_step,
        ),
    )

    with pytest.raises(HomeAssistantError):
        await _mock_backup_generation(manager)
