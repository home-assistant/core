"""Tests for the Marketplace backup helper."""

from pathlib import Path

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.utils.backup import Backup


def test_backup_file(marketplace: MarketplaceManager, tmp_path: Path) -> None:
    """Test backing a single file up and restoring it."""
    target = tmp_path / "target_file"
    target.touch()
    backup = Backup(marketplace=marketplace, local_path=str(target))

    backup.create()
    assert not target.exists()
    assert Path(backup.backup_path_full).exists()

    backup.restore()
    assert target.exists()

    backup.cleanup()
    assert not Path(backup.backup_path_full).exists()


def test_backup_directory(marketplace: MarketplaceManager, tmp_path: Path) -> None:
    """Test backing a directory up and restoring it."""
    target = tmp_path / "target_directory"
    target.mkdir()
    backup = Backup(marketplace=marketplace, local_path=str(target))

    backup.create()
    assert not target.exists()
    assert Path(backup.backup_path_full).exists()

    backup.restore()
    assert target.exists()

    backup.cleanup()
    assert not Path(backup.backup_path_full).exists()


def test_backup_without_source(marketplace: MarketplaceManager, tmp_path: Path) -> None:
    """Test backing up a path that is not there does nothing."""
    backup = Backup(marketplace=marketplace, local_path=str(tmp_path / "missing"))

    backup.create()
    backup.create()

    assert not Path(backup.backup_path_full).exists()
