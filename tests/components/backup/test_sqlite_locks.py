"""Regression tests for SQLite locks during Core backups."""

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
from unittest.mock import patch

import pytest
from securetar import AddFileError

from homeassistant.components.backup.manager import CoreBackupReaderWriter
from homeassistant.core import HomeAssistant


def _sqlite_locks(path: Path) -> list[str]:
    """Find POSIX locks held by this process on a specific SQLite file."""
    inode = path.stat().st_ino
    return [
        line
        for line in Path("/proc/locks").read_text().splitlines()
        if f" {os.getpid()} " in line and f":{inode} " in line
    ]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux POSIX lock regression")
@pytest.mark.parametrize(
    "db_filename", ["home-assistant_v2.db", "custom_recorder.db", "nonstandard_file"]
)
def test_core_backup_preserves_sqlite_locks(
    hass: HomeAssistant, tmp_path: Path, db_filename: str
) -> None:
    """Archiving any SQLite file must not revoke Recorder's POSIX locks."""
    db_path = Path(hass.config.path(db_filename))

    with closing(sqlite3.connect(db_path)) as recorder:
        recorder.execute("PRAGMA journal_mode=WAL")
        recorder.execute("CREATE TABLE events(value TEXT)")
        recorder.execute("INSERT INTO events VALUES ('before')")
        recorder.commit()

        assert _sqlite_locks(db_path), "Recorder must hold a lock before backup"

        # The tmp_backups directory is excluded from the archive itself.
        tar_path = tmp_path / "tmp_backups" / "test-backup.tar"
        CoreBackupReaderWriter(hass)._mkdir_and_generate_backup_contents(
            {"slug": "sqlite-lock-regression"},
            database_included=True,
            password=None,
            tar_file_path=tar_path,
        )

        assert _sqlite_locks(db_path), (
            "Core backup opened and closed the live SQLite file in the "
            "same process, releasing Recorder's POSIX locks"
        )

        with tarfile.open(tar_path) as outer_tar:
            core_archive = outer_tar.extractfile("homeassistant.tar.gz")
            assert core_archive is not None
            with tarfile.open(fileobj=core_archive, mode="r:gz") as core_tar:
                assert f"data/{db_filename}" in core_tar.getnames()
                assert f"data/{db_filename}-wal" in core_tar.getnames()

        with closing(sqlite3.connect(db_path)) as other_connection:
            assert other_connection.execute(
                "SELECT count(*) FROM events"
            ).fetchone() == (1,)

        recorder.execute("INSERT INTO events VALUES ('after')")
        recorder.commit()

        with closing(sqlite3.connect(db_path)) as other_connection:
            assert other_connection.execute(
                "SELECT count(*) FROM events"
            ).fetchone() == (2,)


def test_core_backup_uses_one_reader_process(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """All regular file contents should be streamed through one child."""
    Path(hass.config.path("first.txt")).write_text("first")
    Path(hass.config.path("second.txt")).write_text("second")
    archive_path = tmp_path / "tmp_backups" / "files.tar"

    with patch(
        "homeassistant.components.backup.manager.subprocess.Popen",
        wraps=subprocess.Popen,
    ) as popen:
        CoreBackupReaderWriter(hass)._mkdir_and_generate_backup_contents(
            {"slug": "one-child"},
            database_included=False,
            password=None,
            tar_file_path=archive_path,
        )

    assert popen.call_count == 1
    with tarfile.open(archive_path) as outer:
        stream = outer.extractfile("homeassistant.tar.gz")
        assert stream is not None
        with stream, tarfile.open(fileobj=stream, mode="r:gz") as inner:
            for filename, expected in (
                ("first.txt", b"first"),
                ("second.txt", b"second"),
            ):
                content = inner.extractfile(f"data/{filename}")
                assert content is not None
                with content:
                    assert content.read() == expected


def test_core_backup_rejects_truncated_file(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Do not silently accept files shortened after their tar header is read."""
    source = Path(hass.config.path("shrinking_file"))
    source.write_bytes(b"a" * 8192)
    original_gettarinfo = tarfile.TarFile.gettarinfo
    source_modified = False

    def truncate_after_stat(
        archive: tarfile.TarFile,
        name: str,
        arcname: str | None = None,
        fileobj: None = None,
    ) -> tarfile.TarInfo | None:
        nonlocal source_modified
        info = original_gettarinfo(archive, name, arcname, fileobj)
        if str(name) == str(source):
            source.write_bytes(b"a")
            source_modified = True
        return info

    with (
        patch.object(tarfile.TarFile, "gettarinfo", truncate_after_stat),
        pytest.raises(AddFileError) as exc_info,
    ):
        CoreBackupReaderWriter(hass)._mkdir_and_generate_backup_contents(
            {"slug": "short-file"},
            database_included=False,
            password=None,
            tar_file_path=tmp_path / "tmp_backups" / "short.tar",
        )
    assert source_modified
    assert any(
        "Source changed during backup" in note for note in exc_info.value.__notes__
    )
