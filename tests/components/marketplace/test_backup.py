"""Tests for the Marketplace backup helper."""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.utils.backup import (
    BACKUP_DIRECTORY,
    TARGET_FILE,
    Backup,
    restore_interrupted_backups,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from . import setup_integration

from tests.common import MockConfigEntry


def _backup_root(config_dir: Path) -> Path:
    """Return where the backups are kept."""
    return config_dir / STORAGE_DIR / BACKUP_DIRECTORY


def _integration(config_dir: Path, name: str = "example") -> Path:
    """Create an installed integration and return its directory."""
    directory = config_dir / "custom_components" / name
    directory.mkdir(parents=True)
    (directory / "__init__.py").write_text("installed")
    return directory


def test_backup_directory(marketplace: MarketplaceManager, config_dir: Path) -> None:
    """Test a directory is moved into the backup and put back."""
    target = _integration(config_dir)
    backup = Backup(marketplace, target)

    backup.create()
    assert not target.exists()
    assert (backup.content_path / "__init__.py").read_text() == "installed"
    assert backup.backup_path.parent == _backup_root(config_dir)
    assert (backup.backup_path / TARGET_FILE).read_text() == (
        "custom_components/example"
    )

    backup.restore()
    assert (target / "__init__.py").read_text() == "installed"

    backup.cleanup()
    assert not backup.backup_path.exists()


def test_backup_file(marketplace: MarketplaceManager, config_dir: Path) -> None:
    """Test a single file is moved into the backup and put back."""
    target = config_dir / "python_scripts" / "example.py"
    target.parent.mkdir()
    target.write_text("installed")
    backup = Backup(marketplace, target)

    backup.create()
    assert not target.exists()

    backup.restore()
    assert target.read_text() == "installed"


def test_restore_replaces_a_partial_install(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test restoring removes what a failed install left behind."""
    target = _integration(config_dir)
    backup = Backup(marketplace, target)
    backup.create()

    target.mkdir()
    (target / "half_written.py").write_text("broken")
    backup.restore()

    assert sorted(path.name for path in target.iterdir()) == ["__init__.py"]


def test_backups_do_not_share_a_directory(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test two installs at the same time keep their own backups."""
    first = Backup(marketplace, _integration(config_dir, "first"))
    second = Backup(marketplace, _integration(config_dir, "second"))

    first.create()
    second.create()
    first.cleanup()

    assert (second.content_path / "__init__.py").exists()


def test_nothing_to_back_up(marketplace: MarketplaceManager, config_dir: Path) -> None:
    """Test a path that is not there is left alone."""
    backup = Backup(marketplace, config_dir / "missing")

    backup.create()

    assert not backup.backup_path.exists()


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(".", id="config-directory"),
        pytest.param("custom_components", id="custom-components"),
    ],
)
def test_protected_path_is_refused(
    marketplace: MarketplaceManager, config_dir: Path, target: str
) -> None:
    """Test a path that must never move is refused, not skipped."""
    (config_dir / "custom_components").mkdir(exist_ok=True)
    backup = Backup(marketplace, config_dir / target)

    with pytest.raises(MarketplaceError, match="it is protected"):
        backup.create()

    assert not backup.backup_path.exists()
    assert (config_dir / "custom_components").exists()


def test_restore_interrupted_install(
    marketplace: MarketplaceManager,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a backup left behind by a restart is put back."""
    target = _integration(config_dir)
    Backup(marketplace, target).create()
    target.mkdir()
    (target / "half_written.py").write_text("broken")

    assert restore_interrupted_backups(marketplace)

    assert sorted(path.name for path in target.iterdir()) == ["__init__.py"]
    assert list(_backup_root(config_dir).iterdir()) == []
    assert "an install replacing it did not finish" in caplog.text


def test_restore_interrupted_install_with_persistent_directory(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test the persistent directory goes back into the restored content."""
    target = _integration(config_dir)
    (target / "config").mkdir()
    (target / "config" / "settings.yaml").write_text("mine")

    # The persistent directory is moved out before the content is
    Backup(marketplace, target / "config").create()
    Backup(marketplace, target).create()

    restore_interrupted_backups(marketplace)

    assert (target / "__init__.py").read_text() == "installed"
    assert (target / "config" / "settings.yaml").read_text() == "mine"


def test_restore_after_the_persistent_directory_moved_in(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a stop after the kept data went into the new content does not lose it."""
    target = _integration(config_dir)
    (target / "config").mkdir()
    (target / "config" / "settings.yaml").write_text("mine")
    persistent = Backup(marketplace, target / "config")
    persistent.create()
    Backup(marketplace, target).create()

    # The new content is written and the kept data moved into it, then it stops
    target.mkdir()
    (target / "__init__.py").write_text("new version")
    persistent.restore()

    restore_interrupted_backups(marketplace)

    assert (target / "__init__.py").read_text() == "installed"
    assert (target / "config" / "settings.yaml").read_text() == "mine"


def test_restore_removes_empty_backups(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a backup without a target, from a restart before the move, goes away."""
    empty = _backup_root(config_dir) / "empty"
    empty.mkdir(parents=True)

    assert not restore_interrupted_backups(marketplace)

    assert not empty.exists()


def test_restore_leaves_unknown_targets_alone(
    marketplace: MarketplaceManager,
    config_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a backup that points outside the configuration is never touched."""
    outside = tmp_path_factory.mktemp("outside")
    backup = _backup_root(config_dir) / "outside"
    (backup / "content").mkdir(parents=True)
    (backup / TARGET_FILE).write_text(str(outside / "example"))

    restore_interrupted_backups(marketplace)

    assert (backup / "content").exists()
    assert not (outside / "example").exists()
    assert "Leaving backup" in caplog.text


async def test_setup_restores_interrupted_install(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, config_dir: Path
) -> None:
    """Test setting up puts back what an interrupted install moved aside."""
    backup = _backup_root(config_dir) / "interrupted"
    (backup / "content").mkdir(parents=True)
    (backup / "content" / "__init__.py").write_text("installed")
    (backup / TARGET_FILE).write_text("custom_components/example")

    with patch(
        "homeassistant.components.marketplace.async_clear_custom_components_cache"
    ) as clear_cache:
        await setup_integration(hass, mock_config_entry)

    assert (
        config_dir / "custom_components" / "example" / "__init__.py"
    ).read_text() == "installed"
    assert not backup.exists()
    # The loader has to find the integration that is back in place
    clear_cache.assert_called_once_with(hass)
