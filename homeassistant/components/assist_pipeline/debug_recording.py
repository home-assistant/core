"""Clean up the audio that pipeline runs saved to the debug recording directory."""

from collections.abc import Collection
from contextlib import suppress
from datetime import datetime, timedelta
import os
from pathlib import Path
import stat
import time
from typing import TYPE_CHECKING, NamedTuple, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import CONF_DEBUG_RECORDING_DIR, DATA_CONFIG, DOMAIN

DATA_DEBUG_RECORDINGS: HassKey[DebugRecordings] = HassKey(f"{DOMAIN}.debug_recordings")
STORAGE_KEY = f"{DOMAIN}.debug_recordings"
STORAGE_VERSION = 1

ISSUE_LEFT_OVER = "debug_recordings_left_over"
ISSUE_STILL_ENABLED = "debug_recording_still_enabled"
MAX_RECORDING_AGE = timedelta(days=7)
CHECK_INTERVAL = timedelta(days=1)
# The recording thread stops after 5 seconds without audio.
ACTIVE_RUN_TIME = timedelta(minutes=1)
RECORDING_PREFIXES = ("00_wake-", "01_stt-")


class DebugRecordingsData(TypedDict):
    """Stored debug recording directories."""

    recording_dirs: list[str]


class RecordingScan(NamedTuple):
    """The finished recordings, and whether active runs or read errors skipped others."""

    recordings: dict[Path, os.stat_result]
    active: bool
    failed: bool


def _find_run_recordings(
    run_dir: Path, filenames: list[str]
) -> tuple[dict[Path, os.stat_result], bool]:
    """Return the WAV files the debug recording thread wrote in a run directory.

    Also return True when a recording could not be read.
    """
    recordings: dict[Path, os.stat_result] = {}
    failed = False
    for filename in filenames:
        if not filename.startswith(RECORDING_PREFIXES) or not filename.endswith(".wav"):
            continue
        recording = run_dir / filename
        try:
            recording_stat = recording.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            failed = True
            continue
        if stat.S_ISREG(recording_stat.st_mode):
            recordings[recording] = recording_stat
    return recordings, failed


def _dir_id(path: Path) -> tuple[int, int]:
    """Return the device and inode, which are the same for every path to it."""
    dir_stat = path.stat()
    return dir_stat.st_dev, dir_stat.st_ino


def _scan_debug_recordings(
    recording_dir: Path, skip_dirs: Collection[Path]
) -> RecordingScan:
    """Return the finished recordings, and why others were skipped.

    Runs write to [<device_id>/]<pipeline_name>/<monotonic_ns>/ below the
    directory, and pipeline names can contain slashes. Symlinks are not
    followed, so files outside the directory are never returned. The other
    recording directories in skip_dirs are left out, as they can be nested.
    They are compared by inode, as relative paths or `..` can name the same one.
    """
    recordings: dict[Path, os.stat_result] = {}
    active = False
    failed = False
    active_since = time.time() - ACTIVE_RUN_TIME.total_seconds()

    def _on_error(err: OSError) -> None:
        nonlocal failed
        if not isinstance(err, FileNotFoundError):
            failed = True

    skip_ids: set[tuple[int, int]] = set()
    for skip_dir in skip_dirs:
        try:
            skip_ids.add(_dir_id(skip_dir))
        except FileNotFoundError:
            continue
        except OSError:
            # Its recordings can't be told apart, so this directory isn't scanned.
            return RecordingScan({}, active=False, failed=True)

    for dirpath, dirnames, filenames in os.walk(recording_dir, onerror=_on_error):
        run_dir = Path(dirpath)
        try:
            skip = _dir_id(run_dir) in skip_ids
        except OSError as err:
            _on_error(err)
            skip = True
        if skip:
            dirnames.clear()
            continue
        if (
            not run_dir.name.isdigit()
            or len(run_dir.relative_to(recording_dir).parts) < 2
        ):
            continue
        run_recordings, run_failed = _find_run_recordings(run_dir, filenames)
        failed = failed or run_failed
        if all(
            recording_stat.st_mtime < active_since
            for recording_stat in run_recordings.values()
        ):
            recordings.update(run_recordings)
        else:
            active = True
    return RecordingScan(recordings, active, failed)


def find_debug_recordings(
    recording_dir: Path, skip_dirs: Collection[Path]
) -> dict[Path, os.stat_result]:
    """Return the finished recordings the debug recording thread wrote."""
    return _scan_debug_recordings(recording_dir, skip_dirs).recordings


def scan_left_over_dirs(
    skip_dirs_per_dir: dict[Path, list[Path]],
) -> dict[Path, RecordingScan]:
    """Return the scan of each previous directory."""
    return {
        left_over_dir: _scan_debug_recordings(left_over_dir, skip_dirs)
        for left_over_dir, skip_dirs in skip_dirs_per_dir.items()
    }


def delete_debug_recordings(recording_dir: Path, skip_dirs: Collection[Path]) -> None:
    """Delete the WAV files the debug recording thread wrote.

    Raise OSError when recordings could not be read, but not for active runs.
    """
    scan = _scan_debug_recordings(recording_dir, skip_dirs)
    emptied: set[Path] = set()
    for recording in scan.recordings:
        recording.unlink(missing_ok=True)
        emptied.update(
            recording_dir / parent
            for parent in recording.relative_to(recording_dir).parents
            if parent != Path()
        )
    # Deepest first; rmdir only removes the directories that are now empty.
    for directory in sorted(emptied, key=lambda path: len(path.parts), reverse=True):
        with suppress(OSError):
            directory.rmdir()
    if scan.failed:
        raise OSError(f"Could not read all debug recordings in {recording_dir}")


def _issue_placeholders(
    recording_dirs: list[Path], recordings: list[os.stat_result]
) -> dict[str, str]:
    """Return the placeholders describing the recordings."""
    return {
        "count": str(len(recordings)),
        "size": f"{sum(recording.st_size for recording in recordings) / 1_000_000:.1f}",
        "path": ", ".join(str(recording_dir) for recording_dir in recording_dirs),
    }


class DebugRecordings:
    """Track the debug recordings and raise repair issues for them."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self.recording_dir: Path | None = None
        if recording_dir := hass.data[DATA_CONFIG].get(CONF_DEBUG_RECORDING_DIR):
            self.recording_dir = Path(recording_dir)
        # Directories that were configured before and may still hold recordings.
        self.left_over_dirs: list[Path] = []
        self._store = Store[DebugRecordingsData](hass, STORAGE_VERSION, STORAGE_KEY)
        self._stored_dirs: list[Path] = []

    async def async_setup(self) -> None:
        """Load the previous directories and check for recordings."""
        if stored := await self._store.async_load():
            self._stored_dirs = [Path(path) for path in stored["recording_dirs"]]
        self.left_over_dirs = [
            path for path in self._stored_dirs if path != self.recording_dir
        ]
        await self.async_check_left_over()
        if self.recording_dir is not None:
            await self.async_check_still_enabled()
        elif not self.left_over_dirs:
            return
        async_track_time_interval(
            self.hass,
            self._async_check_interval,
            CHECK_INTERVAL,
            cancel_on_shutdown=True,
        )

    def other_dirs(self, recording_dir: Path) -> list[Path]:
        """Return the other directories that may hold recordings."""
        all_dirs = [*self.left_over_dirs]
        if self.recording_dir is not None:
            all_dirs.append(self.recording_dir)
        return [path for path in all_dirs if path != recording_dir]

    async def async_check_left_over(self) -> None:
        """Raise the issue for recordings in directories that are no longer used."""
        scans = await self.hass.async_add_executor_job(
            scan_left_over_dirs,
            {path: self.other_dirs(path) for path in self.left_over_dirs},
        )
        # Skipped recordings may still be there, so check those directories again.
        self.left_over_dirs = [
            path
            for path, scan in scans.items()
            if scan.recordings or scan.active or scan.failed
        ]
        await self._async_save()
        left_over = {
            path: scan.recordings for path, scan in scans.items() if scan.recordings
        }
        if not left_over:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_LEFT_OVER)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_LEFT_OVER,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_LEFT_OVER,
            translation_placeholders=_issue_placeholders(
                list(left_over),
                [
                    recording_stat
                    for recordings in left_over.values()
                    for recording_stat in recordings.values()
                ],
            ),
        )

    async def async_check_still_enabled(self) -> None:
        """Raise the issue when recording has been on for too long."""
        if TYPE_CHECKING:
            assert self.recording_dir is not None
        recordings = await self.hass.async_add_executor_job(
            find_debug_recordings,
            self.recording_dir,
            self.other_dirs(self.recording_dir),
        )
        oldest = min(
            (recording_stat.st_mtime for recording_stat in recordings.values()),
            default=None,
        )
        if oldest is None or time.time() - oldest < MAX_RECORDING_AGE.total_seconds():
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_STILL_ENABLED)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_STILL_ENABLED,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_STILL_ENABLED,
            translation_placeholders=_issue_placeholders(
                [self.recording_dir], list(recordings.values())
            ),
        )

    async def _async_check_interval(self, now: datetime) -> None:
        """Check again once a day, also for recordings skipped as active."""
        if self.left_over_dirs:
            await self.async_check_left_over()
        if self.recording_dir is not None:
            await self.async_check_still_enabled()

    async def _async_save(self) -> None:
        """Store the directories that may hold recordings, if they changed."""
        recording_dirs = list(self.left_over_dirs)
        if self.recording_dir is not None:
            recording_dirs.append(self.recording_dir)
        if recording_dirs == self._stored_dirs:
            return
        self._stored_dirs = recording_dirs
        await self._store.async_save(
            {"recording_dirs": [str(path) for path in recording_dirs]}
        )


@callback
def async_setup_debug_recordings(hass: HomeAssistant) -> None:
    """Set up the checks for kept debug recordings."""
    debug_recordings = hass.data[DATA_DEBUG_RECORDINGS] = DebugRecordings(hass)
    hass.async_create_background_task(
        debug_recordings.async_setup(), "assist_pipeline_check_debug_recordings"
    )
