"""Test methods in backup_restore."""

from pathlib import Path
import tarfile
from unittest import mock

import pytest

from homeassistant import backup_restore

from .common import get_test_config_dir


@pytest.mark.parametrize(
    ("side_effect", "content", "expected"),
    [
        (FileNotFoundError, "", None),
        (None, "", None),
        (
            None,
            '{"path": "test"}',
            backup_restore.RestoreBackupFileContent(backup_file_path=Path("test")),
        ),
    ],
)
def test_reading_the_instruction_contents(
    side_effect: Exception | None,
    content: str,
    expected: backup_restore.RestoreBackupFileContent | None,
) -> None:
    """Test reading the content of the .HA_RESTORE file."""
    with (
        mock.patch(
            "pathlib.Path.read_text",
            return_value=content,
            side_effect=side_effect,
        ),
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


def test_restoring_backup_when_instructions_can_not_be_read() -> None:
    """Test restoring a backup when instructions can not be read."""
    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=None,
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


def test_aborting_for_older_versions() -> None:
    """Test that we abort for older versions."""
    config_dir = Path(get_test_config_dir())
    backup_file_path = Path(config_dir, "backups", "test.tar")

    def _patched_path_read_text(path: Path, **kwargs):
        return '{"homeassistant": {"version": "9999.99.99"}, "compressed": false}'

    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path
            ),
        ),
        mock.patch("securetar.SecureTarFile"),
        mock.patch("homeassistant.backup_restore.TemporaryDirectory"),
        mock.patch("pathlib.Path.read_text", _patched_path_read_text),
        mock.patch("homeassistant.backup_restore.HA_VERSION", "2013.09.17"),
        pytest.raises(
            ValueError,
            match="You need at least Home Assistant version 9999.99.99 to restore this backup",
        ),
    ):
        assert backup_restore.restore_backup(config_dir) is True


def test_removal_of_current_configuration_when_restoring() -> None:
    """Test that we are removing the current configuration directory."""
    config_dir = Path(get_test_config_dir())
    backup_file_path = Path(config_dir, "backups", "test.tar")
    mock_config_dir = [
        {"path": Path(config_dir, ".HA_RESTORE"), "is_file": True},
        {"path": Path(config_dir, ".HA_VERSION"), "is_file": True},
        {"path": Path(config_dir, "backups"), "is_file": False},
        {"path": Path(config_dir, "www"), "is_file": False},
    ]

    def _patched_path_read_text(path: Path, **kwargs):
        return '{"homeassistant": {"version": "2013.09.17"}, "compressed": false}'

    def _patched_path_is_file(path: Path, **kwargs):
        return [x for x in mock_config_dir if x["path"] == path][0]["is_file"]

    def _patched_path_is_dir(path: Path, **kwargs):
        return not [x for x in mock_config_dir if x["path"] == path][0]["is_file"]

    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path
            ),
        ),
        mock.patch("securetar.SecureTarFile"),
        mock.patch("homeassistant.backup_restore.TemporaryDirectory"),
        mock.patch("homeassistant.backup_restore.HA_VERSION", "2013.09.17"),
        mock.patch("pathlib.Path.read_text", _patched_path_read_text),
        mock.patch("pathlib.Path.is_file", _patched_path_is_file),
        mock.patch("pathlib.Path.is_dir", _patched_path_is_dir),
        mock.patch(
            "pathlib.Path.iterdir",
            return_value=[x["path"] for x in mock_config_dir],
        ),
        mock.patch("pathlib.Path.unlink") as unlink_mock,
        mock.patch("shutil.rmtree") as rmtreemock,
    ):
        assert backup_restore.restore_backup(config_dir) is True
        assert unlink_mock.call_count == 2
        assert (
            rmtreemock.call_count == 1
        )  # We have 2 directories in the config directory, but backups is kept

        removed_directories = {Path(call.args[0]) for call in rmtreemock.mock_calls}
        assert removed_directories == {Path(config_dir, "www")}


def test_extracting_the_contents_of_a_backup_file() -> None:
    """Test extracting the contents of a backup file."""
    config_dir = Path(get_test_config_dir())
    backup_file_path = Path(config_dir, "backups", "test.tar")

    def _patched_path_read_text(path: Path, **kwargs):
        return '{"homeassistant": {"version": "2013.09.17"}, "compressed": false}'

    getmembers_mock = mock.MagicMock(
        return_value=[
            tarfile.TarInfo(name="data"),
            tarfile.TarInfo(name="data/../test"),
            tarfile.TarInfo(name="data/.HA_VERSION"),
            tarfile.TarInfo(name="data/.storage"),
            tarfile.TarInfo(name="data/www"),
        ]
    )
    extractall_mock = mock.MagicMock()

    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path
            ),
        ),
        mock.patch(
            "tarfile.open",
            return_value=mock.MagicMock(
                getmembers=getmembers_mock,
                extractall=extractall_mock,
                __iter__=lambda x: iter(getmembers_mock.return_value),
            ),
        ),
        mock.patch("homeassistant.backup_restore.TemporaryDirectory"),
        mock.patch("pathlib.Path.read_text", _patched_path_read_text),
        mock.patch("pathlib.Path.is_file", return_value=False),
        mock.patch("pathlib.Path.iterdir", return_value=[]),
    ):
        assert backup_restore.restore_backup(config_dir) is True
        assert getmembers_mock.call_count == 1
        assert extractall_mock.call_count == 2

        assert {
            member.name for member in extractall_mock.mock_calls[-1].kwargs["members"]
        } == {".HA_VERSION", ".storage", "www"}
