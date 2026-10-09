"""Test methods in backup_restore."""

from io import BytesIO
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
    restore_config = json.loads(
        get_fixture_path(f"core/backup_restore/{restore_config}", None).read_text(
            encoding="utf-8"
        )
    )
    restore_config["path"] = backup_file_path.as_posix()
    restore_file_path.write_text(json.dumps(restore_config), encoding="utf-8")
    assert restore_file_path.exists()

    # Create a directory at the backup file path to simulate
    # the backup file not being a file
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
    restore_config = json.loads(
        get_fixture_path(f"core/backup_restore/{restore_config}", None).read_text(
            encoding="utf-8"
        )
    )
    restore_config["path"] = backup_file_path.as_posix()
    restore_file_path.write_text(json.dumps(restore_config), encoding="utf-8")
    assert restore_file_path.exists()

    get_fixture_path("core/backup_restore/backup_from_future.tar", None).copy_into(
        tmp_path
    )

    with (
        pytest.raises(
            ValueError,
            match=(
                "You need at least Home Assistant version"
                " 9999.99.99 to restore this backup"
            ),
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
    ("backup", "password"),
    [
        ("backup_with_database.tar", None),
        ("backup_with_database_protected_v2.tar", "hunter2"),
        ("backup_with_database_protected_v3.tar", "hunter2"),
    ],
)
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
    backup: str,
    password: str | None,
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

    get_fixture_path(f"core/backup_restore/{backup}", None).copy(backup_file_path)

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
    restore_backup_content.password = password

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


def test_restore_backup_rejects_unsafe_files(tmp_path: Path) -> None:
    """Test that a backup with unsafe paths is rejected."""
    backup_file_path = tmp_path / "backups" / "test.tar"
    backup_file_path.parent.mkdir()
    get_fixture_path(
        "core/backup_restore/malicious_backup_with_database.tar", None
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
        pytest.raises(tarfile.FilterError),
    ):
        backup_restore.restore_backup(tmp_path.as_posix())

    result = restore_result_file_content(tmp_path)
    assert result is not None
    assert result["success"] is False
    assert result["error_type"] in {"AbsolutePathError", "OutsideDestinationError"}


def _tar_member(
    name: str, *, data: bytes = b"", linkname: str | None = None
) -> tuple[tarfile.TarInfo, bytes | None]:
    """Return a tar member and its data."""
    info = tarfile.TarInfo(name=name)
    if linkname is not None:
        info.type = tarfile.SYMTYPE
        info.linkname = linkname
        return info, None
    info.size = len(data)
    return info, data


BACKUP_JSON = json.dumps(
    {"homeassistant": {"version": "0.0.0"}, "compressed": False}
).encode()


@pytest.mark.parametrize(
    ("members", "missing_member"),
    [
        pytest.param([], "backup.json", id="no_backup_json"),
        pytest.param(
            [_tar_member("./backup.json", linkname="/etc/passwd")],
            "backup.json",
            id="backup_json_symlink",
        ),
        pytest.param(
            [_tar_member("./backup.json", data=BACKUP_JSON)],
            "homeassistant.tar",
            id="no_homeassistant_tar",
        ),
        pytest.param(
            [
                _tar_member("./backup.json", data=BACKUP_JSON),
                _tar_member("homeassistant.tar", linkname="/etc/passwd"),
            ],
            "homeassistant.tar",
            id="homeassistant_tar_absolute_symlink",
        ),
        pytest.param(
            [
                _tar_member("./backup.json", data=BACKUP_JSON),
                _tar_member("other.tar", data=b"not a tar"),
                _tar_member("homeassistant.tar", linkname="other.tar"),
            ],
            "homeassistant.tar",
            id="homeassistant_tar_relative_symlink",
        ),
        pytest.param(
            [
                _tar_member("./backup.json", data=BACKUP_JSON),
                # Would escape the destination if the outer tar was extracted
                _tar_member("pwn", linkname="/tmp"),  # noqa: S108
                _tar_member("pwn/ha_escape_target", data=b"pwned"),
            ],
            "homeassistant.tar",
            id="outer_symlink_escape",
        ),
    ],
)
def test_restore_backup_rejects_invalid_outer_members(
    members: list[tuple[tarfile.TarInfo, bytes | None]],
    missing_member: str,
    tmp_path: Path,
) -> None:
    """Test only regular files are read from the outer backup tar."""
    backup_file_path = tmp_path / "backups" / "test.tar"
    backup_file_path.parent.mkdir()

    with tarfile.open(backup_file_path, "w") as tar:
        for info, data in members:
            tar.addfile(info, BytesIO(data) if data is not None else None)

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
        pytest.raises(ValueError, match=f"Backup does not contain {missing_member}"),
    ):
        backup_restore.restore_backup(tmp_path.as_posix())

    assert restore_result_file_content(tmp_path) == {
        "error": f"Backup does not contain {missing_member}",
        "error_type": "ValueError",
        "success": False,
    }
    assert not Path("/tmp/ha_escape_target").exists()  # noqa: S108


@pytest.mark.parametrize(("remove_after_restore"), [True, False])
def test_remove_backup_file_after_restore(
    remove_after_restore: bool, tmp_path: Path
) -> None:
    """Test removing a backup file after restore."""
    backup_file_path = tmp_path / "backups" / "test.tar"
    backup_file_path.parent.mkdir()
    get_fixture_path("core/backup_restore/backup_with_database.tar", None).copy(
        backup_file_path
    )

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
