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
