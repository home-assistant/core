"""Test methods in backup_restore."""

from pathlib import Path
from unittest import mock

import pytest

from homeassistant import backup_restore

from .common import get_test_config_dir


@pytest.mark.parametrize(
    ("exists", "content", "expected"),
    [
        (False, "", None),
        (True, "", backup_restore.RestoreBackupFileContent(backup_file_path=Path(""))),
        (
            True,
            "test;",
            backup_restore.RestoreBackupFileContent(backup_file_path=Path("test")),
        ),
        (
            True,
            "test;;;;",
            backup_restore.RestoreBackupFileContent(backup_file_path=Path("test")),
        ),
    ],
)
def test_reading_the_instruction_contents(
    exists: bool,
    content: str,
    expected: backup_restore.RestoreBackupFileContent | None,
) -> None:
    """Test reading the content of the .HA_RESTORE file."""
    with (
        mock.patch("pathlib.Path.read_text", return_value=content),
        mock.patch("pathlib.Path.exists", return_value=exists),
    ):
        read_content = backup_restore.restore_backup_file_content(
            Path(get_test_config_dir())
        )
        assert read_content == expected


def test_restoring_backup_that_does_not_exist() -> None:
    """Test restoring a backup that does not exist."""
    backup_file_path = Path(get_test_config_dir("backups", "test"))
    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path
            ),
        ),
        mock.patch("pathlib.Path.read_text", side_effect=FileNotFoundError),
        pytest.raises(
            ValueError, match=f"Backup file {backup_file_path} does not exist"
        ),
    ):
        assert backup_restore.restore_backup(Path(get_test_config_dir())) is False


def test_restoring_backup_that_is_not_a_file() -> None:
    """Test restoring a backup that is not a file."""
    backup_file_path = Path(get_test_config_dir("backups", "test"))
    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path
            ),
        ),
        mock.patch("pathlib.Path.exists", return_value=True),
        mock.patch("pathlib.Path.is_file", return_value=False),
        pytest.raises(
            ValueError, match=f"Backup file {backup_file_path} does not exist"
        ),
    ):
        assert backup_restore.restore_backup(Path(get_test_config_dir())) is False
