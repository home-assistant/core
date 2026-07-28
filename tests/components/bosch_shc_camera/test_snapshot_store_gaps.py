"""Tests closing coverage gaps in snapshot_store.py's disk-persistence helpers.

Exercised through the public `save_snapshot`/`load_snapshot`/
`async_remove_all_snapshots` API against a real filesystem path derived from
`hass.config.path` (a real tmp directory for the test `hass` fixture), rather
than mocking file I/O away — the atomic-write/cleanup logic under test only
matters when it actually touches disk.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.bosch_shc_camera.snapshot_store import (
    async_remove_all_snapshots,
    load_snapshot,
    save_snapshot,
)
from homeassistant.core import HomeAssistant

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"
VALID_JPEG = b"\xff\xd8\xff" + b"0" * 200
TOO_SMALL_JPEG = b"tiny"
# One byte over snapshot_store.py's 10 MiB hard cap.
TOO_LARGE_JPEG = b"0" * (10 * 1024 * 1024 + 1)


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use a real per-test temp config dir instead of the shared fixed testing_config.

    snapshot_store.py writes directly to disk via `pathlib.Path` (not through
    HA's own `Store` helper), so the `hass_storage` fixture never intercepts
    it — without this override every test here would read/write the same
    shared `tests/testing_config/.storage/` directory and pollute each other.
    """
    return hass_tmp_config_dir


def _snap_path(hass: HomeAssistant, cam_id: str = CAM_ID) -> Path:
    return (
        Path(hass.config.path(".storage"))
        / "bosch_shc_camera"
        / "snapshots"
        / f"{cam_id}.jpg"
    )


async def test_save_then_load_roundtrips_real_file(hass: HomeAssistant) -> None:
    """A saved snapshot is persisted atomically and loads back byte-identical."""
    await save_snapshot(hass, CAM_ID, VALID_JPEG)

    snap_path = _snap_path(hass)
    assert snap_path.is_file()
    assert snap_path.read_bytes() == VALID_JPEG

    loaded = await load_snapshot(hass, CAM_ID)

    assert loaded == VALID_JPEG


async def test_load_snapshot_missing_file_returns_none(hass: HomeAssistant) -> None:
    """No persisted file for cam_id yields None, not an exception."""
    assert await load_snapshot(hass, CAM_ID) is None


@pytest.mark.parametrize(
    "jpeg",
    [
        pytest.param(TOO_SMALL_JPEG, id="too-small-skipped"),
        pytest.param(TOO_LARGE_JPEG, id="too-large-skipped"),
    ],
)
async def test_save_snapshot_skips_out_of_bounds_sizes(
    hass: HomeAssistant, jpeg: bytes
) -> None:
    """Snapshots smaller than 100 B or larger than 10 MiB are silently skipped."""
    await save_snapshot(hass, CAM_ID, jpeg)

    assert not _snap_path(hass).exists()


async def test_save_snapshot_invalid_cam_id_raises_value_error(
    hass: HomeAssistant,
) -> None:
    """A non-UUID cam_id is rejected before any disk I/O (path-traversal guard)."""
    with pytest.raises(ValueError, match="cam_id must match"):
        await save_snapshot(hass, "../../etc/passwd", VALID_JPEG)


async def test_load_snapshot_invalid_cam_id_raises_value_error(
    hass: HomeAssistant,
) -> None:
    """A non-UUID cam_id is rejected before any disk I/O (path-traversal guard)."""
    with pytest.raises(ValueError, match="cam_id must match"):
        await load_snapshot(hass, "../../etc/passwd")


async def test_sync_save_replace_failure_cleans_up_tmp_file(
    hass: HomeAssistant,
) -> None:
    """A failed atomic rename removes the leftover .tmp file, then re-raises."""
    with (
        patch("pathlib.Path.replace", side_effect=OSError("cross-device link")),
        pytest.raises(OSError, match="cross-device link"),
    ):
        await save_snapshot(hass, CAM_ID, VALID_JPEG)

    tmp_path = _snap_path(hass).with_suffix(".jpg.tmp")
    assert not tmp_path.exists()


async def test_sync_save_replace_and_unlink_both_fail_still_raises_original(
    hass: HomeAssistant,
) -> None:
    """When the cleanup unlink also fails, the ORIGINAL replace() error still propagates."""
    with (
        patch("pathlib.Path.replace", side_effect=OSError("cross-device link")),
        patch("pathlib.Path.unlink", side_effect=OSError("permission denied")),
        pytest.raises(OSError, match="cross-device link"),
    ):
        await save_snapshot(hass, CAM_ID, VALID_JPEG)


async def test_sync_load_oserror_returns_none(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-FileNotFoundError OSError on read is logged and treated as absent."""
    await save_snapshot(hass, CAM_ID, VALID_JPEG)

    with patch("pathlib.Path.read_bytes", side_effect=PermissionError("denied")):
        result = await load_snapshot(hass, CAM_ID)

    assert result is None
    assert "Failed to read snapshot" in caplog.text


async def test_async_remove_all_snapshots_deletes_directory(
    hass: HomeAssistant,
) -> None:
    """Removing all snapshots deletes the whole per-integration snapshot directory."""
    await save_snapshot(hass, CAM_ID, VALID_JPEG)
    snap_dir = _snap_path(hass).parent
    assert snap_dir.is_dir()

    await async_remove_all_snapshots(hass)

    assert not snap_dir.exists()


async def test_async_remove_all_snapshots_on_missing_directory_is_a_noop(
    hass: HomeAssistant,
) -> None:
    """Removing snapshots when nothing was ever saved does not raise."""
    await async_remove_all_snapshots(hass)
