"""Clean up the audio that pipeline runs saved to the debug recording directory."""

from contextlib import suppress
import os
from pathlib import Path

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_DEBUG_RECORDING_DIR,
    DATA_CONFIG,
    DEBUG_RECORDINGS_ISSUE_ID,
    DOMAIN,
)


@callback
def async_get_debug_recording_dir(hass: HomeAssistant) -> Path | None:
    """Return the configured debug recording directory."""
    if debug_recording_dir := hass.data[DATA_CONFIG].get(CONF_DEBUG_RECORDING_DIR):
        return Path(debug_recording_dir)
    return None


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


def delete_debug_recordings(
    recording_dir: Path, older_than: float | None = None
) -> None:
    """Delete the WAV files modified before older_than, or all of them."""
    emptied: set[Path] = set()
    for recording, stat in find_debug_recordings(recording_dir).items():
        if older_than is None or stat.st_mtime < older_than:
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


@callback
def async_update_debug_recordings_issue(
    hass: HomeAssistant, recording_dir: Path, recordings: dict[Path, os.stat_result]
) -> None:
    """Create or delete the repair issue for the kept debug recordings."""
    if not recordings:
        ir.async_delete_issue(hass, DOMAIN, DEBUG_RECORDINGS_ISSUE_ID)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        DEBUG_RECORDINGS_ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=DEBUG_RECORDINGS_ISSUE_ID,
        translation_placeholders={
            "count": str(len(recordings)),
            "size": f"{sum(stat.st_size for stat in recordings.values()) / 1_000_000:.1f}",
            "path": str(recording_dir),
        },
    )


async def async_check_debug_recordings(
    hass: HomeAssistant, recording_dir: Path
) -> None:
    """Raise the repair issue when debug recordings are kept."""
    recordings = await hass.async_add_executor_job(find_debug_recordings, recording_dir)
    async_update_debug_recordings_issue(hass, recording_dir, recordings)
