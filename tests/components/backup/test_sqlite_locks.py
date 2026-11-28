"""Regression tests for SQLite locks during Core backups."""

from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
from unittest.mock import patch
import venv

import pytest
from securetar import AddFileError

from homeassistant.components.backup import DOMAIN, archive_writer
from homeassistant.components.backup.manager import CoreBackupReaderWriter
from homeassistant.components.backup.models import BackupReaderWriterError
from homeassistant.components.backup.services import BackupService
from homeassistant.core import HomeAssistant

from .common import setup_backup_integration


def _sqlite_locks(path: Path) -> list[str]:
    """Find POSIX locks held by this process on a specific SQLite file."""
    inode = path.stat().st_ino
    return [
        line
        for line in Path("/proc/locks").read_text(encoding="utf-8").splitlines()
        if f" {os.getpid()} " in line and f":{inode} " in line
    ]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux POSIX lock regression")
@pytest.mark.parametrize(
    "db_filename", ["home-assistant_v2.db", "custom_recorder.db", "nonstandard_file"]
)
async def test_core_backup_preserves_sqlite_locks(
    hass: HomeAssistant, db_filename: str
) -> None:
    """Archiving any SQLite file must not revoke Recorder's POSIX locks."""
    await setup_backup_integration(hass)
    db_path = Path(hass.config.path(db_filename))

    with closing(sqlite3.connect(db_path)) as recorder:
        recorder.execute("PRAGMA journal_mode=WAL")
        recorder.execute("CREATE TABLE events(value TEXT)")
        recorder.execute("INSERT INTO events VALUES ('before')")
        recorder.commit()

        assert _sqlite_locks(db_path), "Recorder must hold a lock before backup"

        await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)
        await hass.async_block_till_done()
        [tar_path] = Path(hass.config.path("backups")).glob("*.tar")

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


async def test_core_backup_uses_one_archive_process(hass: HomeAssistant) -> None:
    """A public Core backup archives all files in one child process."""
    await setup_backup_integration(hass)
    Path(hass.config.path("first.txt")).write_text("first", encoding="utf-8")
    Path(hass.config.path("second.txt")).write_text("second", encoding="utf-8")

    with patch(
        "homeassistant.components.backup.manager.subprocess.run",
        wraps=subprocess.run,
    ) as runner:
        await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)
        await hass.async_block_till_done()

    assert runner.call_count == 1
    [archive_path] = Path(hass.config.path("backups")).glob("*.tar")
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


def test_archive_worker_rejects_file_truncated_after_stat(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """A changed file must cause the worker to reject the backup."""
    source = Path(hass.config.path("shrinking_file"))
    source.write_bytes(b"a" * 8192)
    archive_path = tmp_path / "truncated.tar"
    request = {
        "archive_path": str(archive_path),
        "config_path": hass.config.path(),
        "excludes": [],
        "buf_size": 4194304,
        "create_version": 3,
        "password": None,
    }
    payload = json.dumps(request).encode() + b"\n" + b'{"slug":"truncate"}'
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
        patch.object(
            archive_writer.sys,
            "stdin",
            io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8"),
        ),
        patch.object(tarfile.TarFile, "gettarinfo", truncate_after_stat),
        pytest.raises(AddFileError, match="unexpected end of data"),
    ):
        archive_writer.main()
    assert source_modified


def test_archive_process_error_reports_stderr(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Child failures must preserve their actual stderr instead of hiding it."""
    archive_path = tmp_path / "tmp_backups" / "failure.tar"
    failing_command = [
        sys.executable,
        "-I",
        "-c",
        'import sys;sys.stderr.write("reader failed: deliberate test error\\n");sys.exit(42)',
    ]
    original_run = subprocess.run

    def fail_in_child(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        return original_run(failing_command, **kwargs)

    with (
        patch(
            "homeassistant.components.backup.manager.subprocess.run",
            side_effect=fail_in_child,
        ),
        patch(
            "homeassistant.components.backup.manager.json_bytes",
            return_value=b"x" * (1024 * 1024),
        ),
        pytest.raises(BackupReaderWriterError, match="deliberate test error"),
    ):
        CoreBackupReaderWriter(hass)._mkdir_and_generate_backup_contents(
            {"slug": "failure"},
            database_included=False,
            password=None,
            tar_file_path=archive_path,
        )


def test_site_startup_output_cannot_contaminate_archive(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Startup code writing stdout cannot alter the generated tar file."""
    environment = tmp_path / "test_env"
    venv.EnvBuilder(with_pip=False).create(environment)
    executable = environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    site_packages = environment / (
        "Lib/site-packages"
        if os.name == "nt"
        else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    original_sites = [path for path in sys.path if path.endswith("site-packages")]
    (site_packages / "inject_stdout.pth").write_text(
        'import sys;sys.stdout.buffer.write(b"CORRUPTION");sys.stdout.flush()\n'
        + "\n".join(original_sites)
        + "\n",
        encoding="utf-8",
    )

    probe = subprocess.run(
        [str(executable), "-I", "-c", "print('ready')"],
        capture_output=True,
        check=True,
    )
    assert b"CORRUPTION" in probe.stdout

    file_path = Path(hass.config.path("uncontaminated.txt"))
    file_path.write_bytes(b"expected bytes")
    archive_path = tmp_path / "tmp_backups" / "hook.tar"
    original_run = subprocess.run

    def run_in_injected_venv(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        assert kwargs["stdout"] == subprocess.DEVNULL
        return original_run([str(executable), *command[1:]], **kwargs)

    with patch(
        "homeassistant.components.backup.manager.subprocess.run",
        side_effect=run_in_injected_venv,
    ):
        CoreBackupReaderWriter(hass)._mkdir_and_generate_backup_contents(
            {"slug": "startup-hook"},
            database_included=False,
            password=None,
            tar_file_path=archive_path,
        )

    with tarfile.open(archive_path) as outer:
        data = outer.extractfile("homeassistant.tar.gz")
        assert data is not None
        with data, tarfile.open(fileobj=data, mode="r:gz") as inner:
            content = inner.extractfile("data/uncontaminated.txt")
            assert content is not None
            with content:
                assert content.read() == b"expected bytes"
