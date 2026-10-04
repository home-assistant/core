"""Clean up the audio that pipeline runs saved to the debug recording directory."""

from contextlib import suppress
from datetime import datetime, timedelta
import os
from pathlib import Path
import time
from typing import TypedDict

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


class DebugRecordingsData(TypedDict):
    """Stored debug recording directories."""

    recording_dirs: list[str]


def find_debug_recordings(recording_dir: Path) -> dict[Path, os.stat_result]:
    """Return the WAV files the debug recording thread wrote."""
    recordings: dict[Path, os.stat_result] = {}
    # Each run writes NN_<stage>-*.wav to its own <monotonic_ns> directory.
    for recording in recording_dir.rglob("[0-9][0-9]_*.wav"):
        if not recording.parent.name.isdigit():
            continue
        with suppress(FileNotFoundError):
            recordings[recording] = recording.stat()
    return recordings


def find_left_over_recordings(
    recording_dirs: list[Path],
) -> dict[Path, dict[Path, os.stat_result]]:
    """Return the recordings per directory, for directories that still have any."""
    return {
        recording_dir: recordings
        for recording_dir in recording_dirs
        if (recordings := find_debug_recordings(recording_dir))
    }


def delete_debug_recordings(recording_dir: Path) -> None:
    """Delete the WAV files the debug recording thread wrote."""
    emptied: set[Path] = set()
    for recording in find_debug_recordings(recording_dir):
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


def _issue_placeholders(
    recording_dirs: list[Path], recordings: list[os.stat_result]
) -> dict[str, str]:
    """Return the placeholders describing the recordings."""
    return {
        "count": str(len(recordings)),
        "size": f"{sum(stat.st_size for stat in recordings) / 1_000_000:.1f}",
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
        if self.recording_dir is None:
            return
        await self.async_check_still_enabled()
        async_track_time_interval(
            self.hass,
            self._async_check_still_enabled_interval,
            CHECK_INTERVAL,
            cancel_on_shutdown=True,
        )

    async def async_check_left_over(self) -> None:
        """Raise the issue for recordings in directories that are no longer used."""
        left_over = await self.hass.async_add_executor_job(
            find_left_over_recordings, self.left_over_dirs
        )
        self.left_over_dirs = list(left_over)
        await self._async_save()
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
                self.left_over_dirs,
                [
                    stat
                    for recordings in left_over.values()
                    for stat in recordings.values()
                ],
            ),
        )

    async def async_check_still_enabled(self) -> None:
        """Raise the issue when recording has been on for too long."""
        assert self.recording_dir is not None
        recordings = await self.hass.async_add_executor_job(
            find_debug_recordings, self.recording_dir
        )
        oldest = min((stat.st_mtime for stat in recordings.values()), default=None)
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

    async def _async_check_still_enabled_interval(self, now: datetime) -> None:
        """Check the recording age once a day."""
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
