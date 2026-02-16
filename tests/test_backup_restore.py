"""Test methods in backup_restore."""

import json
from pathlib import Path
import tarfile
from typing import Any
from unittest import mock

import pytest

from homeassistant import backup_restore

from .common import get_fixture_path


def restore_result_file_content(config_dir: Path) -> dict[str, Any] | None:
    """Return the content of the restore result file."""
    try:
        return json.loads((config_dir / ".HA_RESTORE_RESULT").read_text("utf-8"))
    except FileNotFoundError:
        return None


@pytest.mark.parametrize(
    ("restore_config", "expected", "restore_result"),
    [
        (
            "restore1.json",  # Empty file, so JSONDecodeError is expected
            None,
            {
                "success": False,
                "error": "Expecting value: line 1 column 1 (char 0)",
                "error_type": "JSONDecodeError",
            },
        ),
        (
            "restore2.json",  # File missing the 'password' key, so KeyError is expected
            None,
            {"success": False, "error": "'password'", "error_type": "KeyError"},
        ),
        (
            "restore3.json",  # Valid file
            backup_restore.RestoreBackupFileContent(
                backup_file_path=Path("test"),
                password="psw",
                remove_after_restore=False,
                restore_database=False,
                restore_homeassistant=True,
            ),
            None,
        ),
        (
            "restore4.json",  # Valid file
            backup_restore.RestoreBackupFileContent(
                backup_file_path=Path("test"),
                password=None,
                remove_after_restore=True,
                restore_database=True,
                restore_homeassistant=False,
            ),
            None,
        ),
    ],
)
def test_reading_the_instruction_contents(
    restore_config: str,
    expected: backup_restore.RestoreBackupFileContent | None,
    restore_result: dict[str, Any] | None,
    tmp_path: Path,
) -> None:
    """Test reading the content of the .HA_RESTORE file."""
    get_fixture_path(f"core/backup_restore/{restore_config}", None).copy(
        tmp_path / ".HA_RESTORE"
    )
    restore_file_path = tmp_path / ".HA_RESTORE"
    assert restore_file_path.exists()

    read_content = backup_restore.restore_backup_file_content(tmp_path)
    assert read_content == expected
    assert not restore_file_path.exists()
    assert restore_result_file_content(tmp_path) == restore_result


def test_reading_the_instruction_contents_missing(tmp_path: Path) -> None:
    """Test reading the content of the .HA_RESTORE file when it is missing."""
    assert not (tmp_path / ".HA_RESTORE").exists()

    read_content = backup_restore.restore_backup_file_content(tmp_path)
    assert read_content is None
    assert not (tmp_path / ".HA_RESTORE").exists()
    assert restore_result_file_content(tmp_path) is None


@pytest.mark.parametrize(
    ("restore_config"),
    [
        "restore3.json",
        "restore4.json",
    ],
)
def test_restoring_backup_that_does_not_exist(
    restore_config: str, tmp_path: Path
) -> None:
    """Test restoring a backup that does not exist."""
    get_fixture_path(f"core/backup_restore/{restore_config}", None).copy(
        tmp_path / ".HA_RESTORE"
    )
    restore_file_path = tmp_path / ".HA_RESTORE"
    assert restore_file_path.exists()
    with (
        pytest.raises(ValueError, match="Backup file test does not exist"),
    ):
        assert backup_restore.restore_backup(tmp_path.as_posix()) is False
    assert restore_result_file_content(tmp_path) == {
        "error": "Backup file test does not exist",
        "error_type": "ValueError",
        "success": False,
    }


@pytest.mark.parametrize(
    ("restore_config", "restore_result"),
    [
        (
            "restore1.json",  # Empty file, so JSONDecodeError is expected
            {
                "success": False,
                "error": "Expecting value: line 1 column 1 (char 0)",
                "error_type": "JSONDecodeError",
            },
        ),
        (
            "restore2.json",  # File missing the 'password' key, so KeyError is expected
            {"success": False, "error": "'password'", "error_type": "KeyError"},
        ),
    ],
)
def test_restoring_backup_when_instructions_can_not_be_read(
    restore_config: str, restore_result: dict[str, Any], tmp_path: Path
) -> None:
    """Test restoring a backup when instructions can not be read."""
    get_fixture_path(f"core/backup_restore/{restore_config}", None).copy(
        tmp_path / ".HA_RESTORE"
    )
    restore_file_path = tmp_path / ".HA_RESTORE"
    assert restore_file_path.exists()
    assert backup_restore.restore_backup(tmp_path.as_posix()) is False
    assert not restore_file_path.exists()
    assert restore_result_file_content(tmp_path) == restore_result


def test_restoring_backup_when_instructions_missing(tmp_path: Path) -> None:
    """Test restoring a backup when instructions are missing."""
    restore_file_path = tmp_path / ".HA_RESTORE"
    assert not restore_file_path.exists()
    assert backup_restore.restore_backup(tmp_path.as_posix()) is False
    assert not restore_file_path.exists()
    assert restore_result_file_content(tmp_path) is None


@pytest.mark.parametrize(
    ("restore_config"),
    [
        "restore3.json",
        "restore4.json",
    ],
)
def test_restoring_backup_that_is_not_a_file(
    restore_config: str, tmp_path: Path
) -> None:
    """Test restoring a backup that is not a file."""
    backup_file_path = tmp_path / "test"
    restore_file_path = tmp_path / ".HA_RESTORE"

    # Set up restore file to point to a file within the temporary directory
    restore_config = json.load(
        get_fixture_path(f"core/backup_restore/{restore_config}", None).open(
            "r", encoding="utf-8"
        )
    )
    restore_config["path"] = backup_file_path.as_posix()
    json.dump(restore_config, restore_file_path.open("w", encoding="utf-8"))
    assert restore_file_path.exists()

    # Create a directory at the backup file path to simulate the backup file not being a file
    backup_file_path.mkdir(exist_ok=True)

    with (
        pytest.raises(IsADirectoryError, match="\\[Errno 21\\] Is a directory"),
    ):
        assert backup_restore.restore_backup(tmp_path.as_posix()) is False
    restore_result = restore_result_file_content(tmp_path)
    assert restore_result == {
        "error": mock.ANY,
        "error_type": "IsADirectoryError",
        "success": False,
    }
    assert restore_result["error"].startswith("[Errno 21] Is a directory:")


@pytest.mark.parametrize(
    ("restore_config"),
    [
        "restore3.json",
        "restore4.json",
    ],
)
def test_aborting_for_older_versions(restore_config: str, tmp_path: Path) -> None:
    """Test that we abort for older versions."""
    backup_file_path = tmp_path / "backup_from_future.tar"
    restore_file_path = tmp_path / ".HA_RESTORE"

    # Set up restore file to point to a file within the temporary directory
    restore_config = json.load(
        get_fixture_path(f"core/backup_restore/{restore_config}", None).open(
            "r", encoding="utf-8"
        )
    )
    restore_config["path"] = backup_file_path.as_posix()
    json.dump(restore_config, restore_file_path.open("w", encoding="utf-8"))
    assert restore_file_path.exists()

    get_fixture_path("core/backup_restore/backup_from_future.tar", None).copy_into(
        tmp_path
    )

    with (
        pytest.raises(
            ValueError,
            match="You need at least Home Assistant version 9999.99.99 to restore this backup",
        ),
    ):
        assert backup_restore.restore_backup(tmp_path.as_posix()) is True
    assert restore_result_file_content(tmp_path) == {
        "error": (
            "You need at least Home Assistant version 9999.99.99 to restore this backup"
        ),
        "error_type": "ValueError",
        "success": False,
    }


@pytest.mark.parametrize(
    (
        "restore_backup_content",
        "expected_kept_files",
        "expected_restored_files",
        "expected_directories_after_restore",
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
            {"backups/test.tar"},
            {"home-assistant_v2.db", "home-assistant_v2.db-wal"},
            {"backups"},
        ),
        (
            backup_restore.RestoreBackupFileContent(
                backup_file_path=None,
                password=None,
                restore_database=False,
                remove_after_restore=False,
                restore_homeassistant=True,
            ),
            {"backups/test.tar", "home-assistant_v2.db", "home-assistant_v2.db-wal"},
            set(),
            {"backups"},
        ),
        (
            backup_restore.RestoreBackupFileContent(
                backup_file_path=None,
                password=None,
                restore_database=True,
                remove_after_restore=False,
                restore_homeassistant=False,
            ),
            {".HA_RESTORE", ".HA_VERSION", "backups/test.tar"},
            {"home-assistant_v2.db", "home-assistant_v2.db-wal"},
            {"backups", "tmp_backups", "www"},
        ),
    ],
)
def test_restore_backup(
    restore_backup_content: backup_restore.RestoreBackupFileContent,
    expected_kept_files: set[str],
    expected_restored_files: set[str],
    expected_directories_after_restore: set[str],
    tmp_path: Path,
) -> None:
    """Test restoring a backup.

    This includes checking that expected files are kept, restored, and
    that we are cleaning up the current configuration directory.
    """
    backup_file_path = tmp_path / "backups" / "test.tar"

    def get_files(path: Path) -> set[str]:
        """Get all files under path."""
        return {str(f.relative_to(path)) for f in path.rglob("*")}

    existing_dirs = {
        "backups",
        "tmp_backups",
        "www",
    }
    existing_files = {
        ".HA_RESTORE",
        ".HA_VERSION",
        "home-assistant_v2.db",
        "home-assistant_v2.db-wal",
    }

    for d in existing_dirs:
        (tmp_path / d).mkdir(exist_ok=True)
    for f in existing_files:
        (tmp_path / f).write_text("before_restore")

    get_fixture_path(
        "core/backup_restore/empty_backup_database_included.tar", None
    ).copy(backup_file_path)

    files_before_restore = get_files(tmp_path)
    assert files_before_restore == {
        ".HA_RESTORE",
        ".HA_VERSION",
        "backups",
        "backups/test.tar",
        "home-assistant_v2.db",
        "home-assistant_v2.db-wal",
        "tmp_backups",
        "www",
    }
    kept_files_data = {}
    for file in expected_kept_files:
        kept_files_data[file] = (tmp_path / file).read_bytes()

    restore_backup_content.backup_file_path = backup_file_path

    with (
        mock.patch(
            "homeassistant.backup_restore.restore_backup_file_content",
            return_value=restore_backup_content,
        ),
    ):
        assert backup_restore.restore_backup(tmp_path.as_posix()) is True

    files_after_restore = get_files(tmp_path)
    assert (
        files_after_restore
        == {".HA_RESTORE_RESULT"}
        | expected_kept_files
        | expected_restored_files
        | expected_directories_after_restore
    )

    for d in expected_directories_after_restore:
        assert (tmp_path / d).is_dir()
    for file in expected_kept_files:
        assert (tmp_path / file).read_bytes() == kept_files_data[file]
    for file in expected_restored_files:
        assert (tmp_path / file).read_bytes() == b"restored_from_backup"

    assert restore_result_file_content(tmp_path) == {
        "error": None,
        "error_type": None,
        "success": True,
    }


def test_restore_backup_filter_files(tmp_path: Path) -> None:
    """Test filtering dangerous files when restoring a backup."""
    backup_file_path = tmp_path / "backups" / "test.tar"
    backup_file_path.parent.mkdir()
    get_fixture_path(
        "core/backup_restore/empty_backup_database_included.tar", None
    ).copy(backup_file_path)

    with (
        tarfile.open(backup_file_path, "r") as outer_tar,
        tarfile.open(
            fileobj=outer_tar.extractfile("homeassistant.tar.gz"), mode="r|gz"
        ) as inner_tar,
    ):
        member_names = {member.name for member in inner_tar.getmembers()}
        assert member_names == {
            ".",
            "../bad_file_with_parent_link",
            "/bad_absolute_file",
            "data",
            "data/home-assistant_v2.db",
            "data/home-assistant_v2.db-wal",
        }

    real_extractone = tarfile.TarFile._extract_one

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
            "tarfile.TarFile._extract_one", autospec=True, wraps=real_extractone
        ) as extractone_mock,
    ):
        assert backup_restore.restore_backup(tmp_path.as_posix()) is True

    # Check the unsafe files are not extracted, and that the safe files are extracted
    extracted_files = {call.args[1].name for call in extractone_mock.mock_calls}
    assert extracted_files == {
        "./backup.json",  # From the outer tar
        "homeassistant.tar.gz",  # From the outer tar
        ".",
        "data",
        "data/home-assistant_v2.db",
        "data/home-assistant_v2.db-wal",
    }
    assert restore_result_file_content(tmp_path) == {
        "error": None,
        "error_type": None,
        "success": True,
    }


@pytest.mark.parametrize(("remove_after_restore"), [True, False])
def test_remove_backup_file_after_restore(
    remove_after_restore: bool, tmp_path: Path
) -> None:
    """Test removing a backup file after restore."""
    backup_file_path = tmp_path / "backups" / "test.tar"
    backup_file_path.parent.mkdir()
    get_fixture_path(
        "core/backup_restore/empty_backup_database_included.tar", None
    ).copy(backup_file_path)

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
    ):
        assert backup_restore.restore_backup(tmp_path.as_posix()) is True
    assert backup_file_path.exists() == (not remove_after_restore)
    assert restore_result_file_content(tmp_path) == {
        "error": None,
        "error_type": None,
        "success": True,
    }


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
