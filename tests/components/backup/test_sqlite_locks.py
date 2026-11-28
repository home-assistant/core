"""Regression tests for SQLite locks during Core backups."""

from contextlib import closing
import fcntl
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

import pytest
from securetar import AddFileError

from homeassistant.components.backup import DOMAIN, archive_writer
from homeassistant.components.backup.models import BackupManagerError
from homeassistant.components.backup.services import BackupService
from homeassistant.components.backup.util import (
    cleanup_stale_backup_archives,
    create_backup_staging_file,
    read_backup,
)
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


async def test_backup_setup_cleans_stale_stages_but_skips_active(
    hass: HomeAssistant,
) -> None:
    """Recover abandoned archives without deleting an in-progress worker file."""
    backup_dir = Path(hass.config.path("backups"))
    temp_dir = Path(hass.config.path("tmp_backups"))
    backup_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)
    old_local = backup_dir / ".ha-backup-oldlocal.partial"
    old_temporary = temp_dir / ".ha-backup-oldtemporary.partial"
    active = backup_dir / ".ha-backup-live.partial"
    old_local.write_bytes(b"old local archive")
    old_temporary.write_bytes(b"old temporary archive")
    active.write_bytes(b"active archive")

    with active.open("rb") as active_file:
        fcntl.flock(active_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        await setup_backup_integration(hass)
        assert not old_local.exists()
        assert not old_temporary.exists()
        assert active.read_bytes() == b"active archive"

    await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)
    assert not active.exists()


def test_staging_lock_survives_parent_exit(tmp_path: Path) -> None:
    """A cleanup process must not remove output owned by a surviving child."""
    fd, staging_path = create_backup_staging_file(tmp_path)
    child_code = (
        "import os, sys; "
        "os.fstat(int(sys.argv[1])); "
        "print('READY', flush=True); "
        "sys.stdin.buffer.read(1)"
    )
    try:
        with subprocess.Popen(
            [sys.executable, "-P", "-c", child_code, str(fd)],
            pass_fds=(fd,),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as child:
            assert child.stdin is not None
            assert child.stdout is not None
            assert child.stdout.readline() == b"READY\n"
            os.close(fd)
            fd = -1
            cleanup_stale_backup_archives(tmp_path)
            assert staging_path.exists()
            child.stdin.write(b"x")
            child.stdin.flush()
            assert child.wait(timeout=5) == 0
        cleanup_stale_backup_archives(tmp_path)
        assert not staging_path.exists()
    finally:
        if fd != -1:
            os.close(fd)


async def test_core_backup_archive_permissions_follow_umask(
    hass: HomeAssistant,
) -> None:
    """A published backup should have normal umask-derived file permissions."""
    await setup_backup_integration(hass)
    backup_dir = Path(hass.config.path("backups"))
    reference = backup_dir / "permission-reference"
    reference.touch()

    with patch(
        "homeassistant.components.backup.manager.subprocess.run",
        wraps=subprocess.run,
    ) as runner:
        await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)

    [archive] = backup_dir.glob("*.tar")
    assert stat.S_IMODE(archive.stat().st_mode) == stat.S_IMODE(
        reference.stat().st_mode
    )
    assert len(runner.call_args.kwargs["pass_fds"]) == 1


async def test_core_backup_uses_one_archive_process(hass: HomeAssistant) -> None:
    """A public Core backup archives all files in one child process."""
    await setup_backup_integration(hass)
    Path(hass.config.path("first.txt")).write_text("first", encoding="utf-8")
    Path(hass.config.path("second.txt")).write_text("second", encoding="utf-8")
    # An active staging file is skipped by cleanup and excluded from archives.
    active_stage = Path(hass.config.path("backups/.ha-backup-orphan.partial"))
    active_stage.write_bytes(b"incomplete archive")

    # -P runs Python site hooks, which can print to stdout. No stdout bytes
    # from the child should be mistaken for part of the archive.
    active_file = await hass.async_add_executor_job(active_stage.open, "rb")
    with (
        active_file,
        tempfile.TemporaryDirectory() as startup_dir,
        patch.dict(
            os.environ,
            {
                "PYTHONPATH": f"{startup_dir}{os.pathsep}"
                f"{os.environ.get('PYTHONPATH', '')}"
            },
        ),
    ):
        fcntl.flock(active_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        Path(startup_dir, "sitecustomize.py").write_text(
            'import sys; sys.stdout.write("CORRUPTION"); sys.stdout.flush()\n',
            encoding="utf-8",
        )
        probe = await hass.async_add_executor_job(
            subprocess.check_output,
            [sys.executable, "-P", "-c", "print('ready')"],
        )
        assert b"CORRUPTION" in probe
        with patch(
            "homeassistant.components.backup.manager.subprocess.run",
            wraps=subprocess.run,
        ) as runner:
            await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)
            await hass.async_block_till_done()
        assert active_stage.read_bytes() == b"incomplete archive"

    assert runner.call_count == 1
    assert runner.call_args.args[0][1] == "-P"
    assert runner.call_args.kwargs["stdout"] == subprocess.DEVNULL
    request = json.loads(runner.call_args.kwargs["input"].split(b"\n", 1)[0])
    assert request["archive_path"].endswith(".partial")
    assert active_stage.exists()
    [archive_path] = Path(hass.config.path("backups")).glob("*.tar")
    with tarfile.open(archive_path) as outer:
        stream = outer.extractfile("homeassistant.tar.gz")
        assert stream is not None
        with stream, tarfile.open(fileobj=stream, mode="r:gz") as inner:
            assert not any(name.endswith(".partial") for name in inner.getnames())
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
        "excludes": [archive_path.name],
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


async def test_core_backup_reports_worker_early_exit(hass: HomeAssistant) -> None:
    """Public backup creation reports the child's status and stderr on failure."""
    await setup_backup_integration(hass)
    failing_command = [
        sys.executable,
        "-P",
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
        pytest.raises(BackupManagerError, match="exit code 42") as exc_info,
    ):
        await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)

    assert "deliberate test error" in str(exc_info.value)


async def test_core_backup_does_not_publish_partial_archive(
    hass: HomeAssistant,
) -> None:
    """A worker dying after backup.json must not leave a discoverable backup."""
    await setup_backup_integration(hass)
    original_run = subprocess.run
    partially_written = False
    worker = (
        "import io, json, os, sys, tarfile; "
        "request = json.loads(sys.stdin.buffer.readline()); "
        "metadata = sys.stdin.buffer.read(); "
        "archive = tarfile.open(request['archive_path'], 'w'); "
        "info = tarfile.TarInfo('./backup.json'); "
        "info.size = len(metadata); "
        "archive.addfile(info, io.BytesIO(metadata)); "
        "archive.close(); "
        "os._exit(37)"
    )

    def fail_after_writing_metadata(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess:
        nonlocal partially_written
        result = original_run([command[0], "-P", "-c", worker], **kwargs)
        request = json.loads(kwargs["input"].split(b"\n", 1)[0])
        partial_path = Path(request["archive_path"])
        assert read_backup(partial_path).homeassistant_included
        partially_written = True
        return result

    with (
        patch(
            "homeassistant.components.backup.manager.subprocess.run",
            side_effect=fail_after_writing_metadata,
        ),
        pytest.raises(BackupManagerError, match="exit code 37"),
    ):
        await hass.services.async_call(DOMAIN, BackupService.CREATE, blocking=True)

    assert partially_written
    assert not list(Path(hass.config.path("backups")).glob("*.tar"))
    assert not list(Path(hass.config.path("backups")).glob("*.partial"))
