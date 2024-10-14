"""Test methods in backup_restore."""

from unittest import mock

import pytest

from homeassistant import backup_restore

from .common import get_test_config_dir


@pytest.mark.parametrize(
    ("exists", "content", "expected"),
    [
        (False, "", None),
        (True, "", backup_restore.RestoreBackupFileContent(backup_file_path="")),
        (
            True,
            "test;",
            backup_restore.RestoreBackupFileContent(backup_file_path="test"),
        ),
        (
            True,
            "test;;;;",
            backup_restore.RestoreBackupFileContent(backup_file_path="test"),
        ),
    ],
)
def test_reading_the_instruction_contents(
    exists: bool,
    content: str,
    expected: backup_restore.RestoreBackupFileContent | None,
) -> None:
    """Test reading the content of the .HA_RESTORE file."""
    mock_open = mock.mock_open()
    with (
        mock.patch("homeassistant.backup_restore.open", mock_open, create=True),
        mock.patch("os.path.exists", return_value=exists),
    ):
        opened_file = mock_open.return_value
        opened_file.readline.return_value = content
        assert (
            backup_restore.restore_backup_file_content(get_test_config_dir())
            == expected
        )
