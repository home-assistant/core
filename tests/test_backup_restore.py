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
            None,
        ),
        (
            None,
            '{"path": "test", "password": "psw", "remove_after_restore": false, "restore_database": false, "restore_homeassistant": true}',
            backup_restore.RestoreBackupFileContent(
                backup_file_path=Path("test"),
                password="psw",
                remove_after_restore=False,
                restore_database=False,
                restore_homeassistant=True,
            ),
        ),
        (
            None,
            '{"path": "test", "password": null, "remove_after_restore": true, "restore_database": true, "restore_homeassistant": false}',
            backup_restore.RestoreBackupFileContent(
                backup_file_path=Path("test"),
                password=None,
                remove_after_restore=True,
                restore_database=True,
                restore_homeassistant=False,
            ),
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
        mock.patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
    ):
        config_path = Path(get_test_config_dir())
        read_content = backup_restore.restore_backup_file_content(config_path)
        assert read_content == expected
        unlink_mock.assert_called_once_with(
            config_path / ".HA_RESTORE", missing_ok=True
        )


def test_restoring_backup_that_does_not_exist() -> None:
    """Test restoring a backup that does not exist."""
    backup_file_path = Path(get_test_config_dir("backups", "test"))
    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path,
                password=None,
                remove_after_restore=False,
                restore_database=True,
                restore_homeassistant=True,
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
                backup_file_path=backup_file_path,
                password=None,
                remove_after_restore=False,
                restore_database=True,
                restore_homeassistant=True,
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
                backup_file_path=backup_file_path,
                password=None,
                remove_after_restore=False,
                restore_database=True,
                restore_homeassistant=True,
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


@pytest.mark.parametrize(
    (
        "restore_backup_content",
        "expected_removed_files",
        "expected_removed_directories",
        "expected_copied_files",
        "expected_copied_trees",
    ),
    [
        (
            backup_restore.RestoreBackupFileContent(
                backup_file_path=None,
                password=None,
                remove_after_restore=False,
                restore_database=True,
                restore_homeassistant=True,
            ),
            (
                ".HA_RESTORE",
                ".HA_VERSION",
                "home-assistant_v2.db",
                "home-assistant_v2.db-wal",
            ),
            ("tmp_backups", "www"),
            (),
            ("data",),
        ),
        (
            backup_restore.RestoreBackupFileContent(
                backup_file_path=None,
                password=None,
                restore_database=False,
                remove_after_restore=False,
                restore_homeassistant=True,
            ),
            (".HA_RESTORE", ".HA_VERSION"),
            ("tmp_backups", "www"),
            (),
            ("data",),
        ),
        (
            backup_restore.RestoreBackupFileContent(
                backup_file_path=None,
                password=None,
                restore_database=True,
                remove_after_restore=False,
                restore_homeassistant=False,
            ),
            ("home-assistant_v2.db", "home-assistant_v2.db-wal"),
            (),
            ("home-assistant_v2.db", "home-assistant_v2.db-wal"),
            (),
        ),
    ],
)
def test_removal_of_current_configuration_when_restoring(
    restore_backup_content: backup_restore.RestoreBackupFileContent,
    expected_removed_files: tuple[str, ...],
    expected_removed_directories: tuple[str, ...],
    expected_copied_files: tuple[str, ...],
    expected_copied_trees: tuple[str, ...],
) -> None:
    """Test that we are removing the current configuration directory."""
    config_dir = Path(get_test_config_dir())
    restore_backup_content.backup_file_path = Path(config_dir, "backups", "test.tar")
    mock_config_dir = [
        {"path": Path(config_dir, ".HA_RESTORE"), "is_file": True},
        {"path": Path(config_dir, ".HA_VERSION"), "is_file": True},
        {"path": Path(config_dir, "home-assistant_v2.db"), "is_file": True},
        {"path": Path(config_dir, "home-assistant_v2.db-wal"), "is_file": True},
        {"path": Path(config_dir, "backups"), "is_file": False},
        {"path": Path(config_dir, "tmp_backups"), "is_file": False},
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
            return_value=restore_backup_content,
        ),
        mock.patch("securetar.SecureTarFile"),
        mock.patch("homeassistant.backup_restore.TemporaryDirectory") as temp_dir_mock,
        mock.patch("homeassistant.backup_restore.HA_VERSION", "2013.09.17"),
        mock.patch("pathlib.Path.read_text", _patched_path_read_text),
        mock.patch("pathlib.Path.is_file", _patched_path_is_file),
        mock.patch("pathlib.Path.is_dir", _patched_path_is_dir),
        mock.patch(
            "pathlib.Path.iterdir",
            return_value=[x["path"] for x in mock_config_dir],
        ),
        mock.patch("pathlib.Path.unlink", autospec=True) as unlink_mock,
        mock.patch("shutil.copy") as copy_mock,
        mock.patch("shutil.copytree") as copytree_mock,
        mock.patch("shutil.rmtree") as rmtree_mock,
    ):
        temp_dir_mock.return_value.__enter__.return_value = "tmp"

        assert backup_restore.restore_backup(config_dir) is True

        tmp_ha = Path("tmp", "homeassistant")
        assert copy_mock.call_count == len(expected_copied_files)
        copied_files = {Path(call.args[0]) for call in copy_mock.mock_calls}
        assert copied_files == {Path(tmp_ha, "data", f) for f in expected_copied_files}

        assert copytree_mock.call_count == len(expected_copied_trees)
        copied_trees = {Path(call.args[0]) for call in copytree_mock.mock_calls}
        assert copied_trees == {Path(tmp_ha, t) for t in expected_copied_trees}

        assert unlink_mock.call_count == len(expected_removed_files)
        removed_files = {Path(call.args[0]) for call in unlink_mock.mock_calls}
        assert removed_files == {Path(config_dir, f) for f in expected_removed_files}

        assert rmtree_mock.call_count == len(expected_removed_directories)
        removed_directories = {Path(call.args[0]) for call in rmtree_mock.mock_calls}
        assert removed_directories == {
            Path(config_dir, d) for d in expected_removed_directories
        }


def test_extracting_the_contents_of_a_backup_file() -> None:
    """Test extracting the contents of a backup file."""
    config_dir = Path(get_test_config_dir())
    backup_file_path = Path(config_dir, "backups", "test.tar")

    def _patched_path_read_text(path: Path, **kwargs):
        return '{"homeassistant": {"version": "2013.09.17"}, "compressed": false}'

    getmembers_mock = mock.MagicMock(
        return_value=[
            tarfile.TarInfo(name="../data/test"),
            tarfile.TarInfo(name="data"),
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
                backup_file_path=backup_file_path,
                password=None,
                remove_after_restore=False,
                restore_database=True,
                restore_homeassistant=True,
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
        mock.patch("shutil.copytree"),
    ):
        assert backup_restore.restore_backup(config_dir) is True
        assert extractall_mock.call_count == 2

        assert {
            member.name for member in extractall_mock.mock_calls[-1].kwargs["members"]
        } == {"data", "data/.HA_VERSION", "data/.storage", "data/www"}


@pytest.mark.parametrize(
    ("remove_after_restore", "unlink_calls"), [(True, 1), (False, 0)]
)
def test_remove_backup_file_after_restore(
    remove_after_restore: bool, unlink_calls: int
) -> None:
    """Test removing a backup file after restore."""
    config_dir = Path(get_test_config_dir())
    backup_file_path = Path(config_dir, "backups", "test.tar")

    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=backup_restore.RestoreBackupFileContent(
                backup_file_path=backup_file_path,
                password=None,
                remove_after_restore=remove_after_restore,
                restore_database=True,
                restore_homeassistant=True,
            ),
        ),
        mock.patch("homeassistant.backup_restore._extract_backup"),
        mock.patch("pathlib.Path.unlink", autospec=True) as mock_unlink,
    ):
        assert backup_restore.restore_backup(config_dir) is True
    assert mock_unlink.call_count == unlink_calls
    for call in mock_unlink.mock_calls:
        assert call.args[0] == backup_file_path


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("test", b"\xf0\x9b\xb9\x1f\xdc,\xff\xd5x\xd6\xd6\x8fz\x19.\x0f"),
        ("lorem ipsum...", b"#\xe0\xfc\xe0\xdb?_\x1f,$\rQ\xf4\xf5\xd8\xfb"),
    ],
)
def test_pw_to_key(password: str | None, expected: bytes | None) -> None:
    """Test password to key conversion."""
    assert backup_restore.password_to_key(password) == expected


def test_pw_to_key_none() -> None:
    """Test password to key conversion."""
    with pytest.raises(AttributeError):
        backup_restore.password_to_key(None)
