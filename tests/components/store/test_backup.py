"""Tests for the Community store backup helper."""

from pathlib import Path

from homeassistant.components.store.base import StoreManager
from homeassistant.components.store.utils.backup import Backup


def test_backup_file(store: StoreManager, tmp_path: Path) -> None:
    """Test backing a single file up and restoring it."""
    target = tmp_path / "target_file"
    target.touch()
    backup = Backup(store=store, local_path=str(target))

    backup.create()
    assert not target.exists()
    assert Path(backup.backup_path_full).exists()

    backup.restore()
    assert target.exists()

    backup.cleanup()
    assert not Path(backup.backup_path_full).exists()


def test_backup_directory(store: StoreManager, tmp_path: Path) -> None:
    """Test backing a directory up and restoring it."""
    target = tmp_path / "target_directory"
    target.mkdir()
    backup = Backup(store=store, local_path=str(target))

    backup.create()
    assert not target.exists()
    assert Path(backup.backup_path_full).exists()

    backup.restore()
    assert target.exists()

    backup.cleanup()
    assert not Path(backup.backup_path_full).exists()


def test_backup_without_source(store: StoreManager, tmp_path: Path) -> None:
    """Test backing up a path that is not there does nothing."""
    backup = Backup(store=store, local_path=str(tmp_path / "missing"))

    backup.create()
    backup.create()

    assert not Path(backup.backup_path_full).exists()
