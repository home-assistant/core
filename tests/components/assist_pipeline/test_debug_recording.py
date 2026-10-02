"""Test cleaning up the Assist pipeline debug recordings."""

from datetime import timedelta
import os
from pathlib import Path
import time
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.assist_pipeline.const import (
    CONF_DEBUG_RECORDING_DIR,
    DOMAIN,
)
from homeassistant.components.assist_pipeline.debug_recording import (
    ISSUE_LEFT_OVER,
    ISSUE_STILL_ENABLED,
    STORAGE_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

WAKE = Path("satellite", "Home Assistant", "1", "00_wake-wake_word.test.wav")
STT = Path("satellite", "Home Assistant", "1", "01_stt-stt.test.wav")
OTHER_RUN_STT = Path("Home Assistant", "2", "01_stt-stt.test.wav")
OTHER_FILE = Path("notes.txt")
OTHER_WAV = Path("sounds", "01_doorbell.wav")
EMPTY_DIR = Path("empty")
KEPT_FILES = [EMPTY_DIR, OTHER_FILE, OTHER_WAV.parent, OTHER_WAV]


def _write_recordings(recording_dir: Path, days_old: int) -> None:
    """Write recordings like the debug recording thread leaves behind."""
    modified = time.time() - days_old * 86400
    for recording in (WAKE, STT, OTHER_RUN_STT):
        path = recording_dir / recording
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0" * 500_000)
        os.utime(path, (modified, modified))
    (recording_dir / OTHER_FILE).write_text("keep")
    (recording_dir / OTHER_WAV).parent.mkdir()
    (recording_dir / OTHER_WAV).write_bytes(b"keep")
    (recording_dir / EMPTY_DIR).mkdir()


def _delete_one_then_fail(recording_dir: Path) -> None:
    """Delete one recording, then fail like a file without write access."""
    (recording_dir / WAKE).unlink()
    raise PermissionError


def _list_files(recording_dir: Path) -> list[Path]:
    """Return the files and directories below the recording directory."""
    return sorted(path.relative_to(recording_dir) for path in recording_dir.rglob("*"))


def _stored_dirs(hass_storage: dict[str, Any]) -> list[str]:
    """Return the stored recording directories."""
    return hass_storage[STORAGE_KEY]["data"]["recording_dirs"]


async def _async_setup(hass: HomeAssistant, recording_dir: Path | None) -> None:
    """Set up Assist pipeline, with or without a debug recording directory."""
    config: dict[str, Any] = {}
    if recording_dir is not None:
        config[CONF_DEBUG_RECORDING_DIR] = str(recording_dir)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
def left_over_dir(tmp_path: Path, hass_storage: dict[str, Any]) -> Path:
    """Return a directory that was used for debug recordings before."""
    _write_recordings(tmp_path, days_old=1)
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"recording_dirs": [str(tmp_path)]},
    }
    return tmp_path


@pytest.mark.usefixtures("init_supporting_components")
async def test_left_over_repair(
    hass: HomeAssistant,
    left_over_dir: Path,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue for recordings left after turning recording off."""
    await _async_setup(hass, None)

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "count": "3",
        "size": "1.5",
        "path": str(left_over_dir),
    }

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_LEFT_OVER)
    assert flow["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow["flow_id"])
    assert result["type"] == "create_entry"

    # Files that aren't recordings, and directories that weren't emptied, are kept.
    assert await hass.async_add_executor_job(_list_files, left_over_dir) == KEPT_FILES
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER) is None
    assert _stored_dirs(hass_storage) == []


@pytest.mark.usefixtures("init_supporting_components")
async def test_left_over_after_changing_directory(
    hass: HomeAssistant,
    left_over_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the previous directory counts as left over after changing it."""
    new_dir = tmp_path_factory.mktemp("new")
    await _async_setup(hass, new_dir)

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER)
    assert issue is not None
    assert issue.translation_placeholders["path"] == str(left_over_dir)
    assert _stored_dirs(hass_storage) == [str(left_over_dir), str(new_dir)]


@pytest.mark.usefixtures("init_supporting_components")
async def test_left_over_deleted_manually(
    hass: HomeAssistant,
    left_over_dir: Path,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a previous directory without recordings is forgotten."""
    await hass.async_add_executor_job(
        lambda: [(left_over_dir / path).unlink() for path in (WAKE, STT, OTHER_RUN_STT)]
    )
    await _async_setup(hass, None)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER) is None
    assert _stored_dirs(hass_storage) == []


@pytest.mark.usefixtures("init_supporting_components")
async def test_left_over_repair_delete_failed(
    hass: HomeAssistant,
    left_over_dir: Path,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix flow aborts when the recordings can't be deleted."""
    await _async_setup(hass, None)
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_LEFT_OVER)
    with patch(
        "homeassistant.components.assist_pipeline.repairs.delete_debug_recordings",
        side_effect=_delete_one_then_fail,
    ):
        result = await process_repair_fix_flow(client, flow["flow_id"])

    assert result["type"] == "abort"
    assert result["reason"] == "delete_failed"
    # The issue shows the recordings that are left.
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER)
    assert issue is not None
    assert issue.translation_placeholders == {
        "count": "2",
        "size": "1.0",
        "path": str(left_over_dir),
    }


@pytest.mark.usefixtures("init_supporting_components")
async def test_still_enabled_repair(
    hass: HomeAssistant,
    tmp_path: Path,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue for recording that was left on for more than 7 days."""
    await hass.async_add_executor_job(_write_recordings, tmp_path, 8)
    await _async_setup(hass, tmp_path)

    assert _stored_dirs(hass_storage) == [str(tmp_path)]
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER) is None
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_STILL_ENABLED)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "count": "3",
        "size": "1.5",
        "path": str(tmp_path),
    }

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_STILL_ENABLED)
    result = await process_repair_fix_flow(client, flow["flow_id"])
    assert result["type"] == "create_entry"

    assert await hass.async_add_executor_job(_list_files, tmp_path) == KEPT_FILES
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_STILL_ENABLED) is None


@pytest.mark.usefixtures("init_supporting_components")
async def test_still_enabled_checked_daily(
    hass: HomeAssistant,
    tmp_path: Path,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the recording age is checked again every day."""
    await hass.async_add_executor_job(_write_recordings, tmp_path, 6)
    await _async_setup(hass, tmp_path)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_STILL_ENABLED) is None

    freezer.tick(timedelta(days=1, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_STILL_ENABLED) is not None


@pytest.mark.usefixtures("init_supporting_components")
async def test_no_debug_recordings(
    hass: HomeAssistant, tmp_path: Path, issue_registry: ir.IssueRegistry
) -> None:
    """Test no issue is created for WAV files that aren't debug recordings."""
    path = tmp_path / "01_doorbell.wav"
    await hass.async_add_executor_job(path.write_bytes, b"")
    modified = time.time() - 30 * 86400
    await hass.async_add_executor_job(os.utime, path, (modified, modified))
    await _async_setup(hass, tmp_path)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_STILL_ENABLED) is None
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_LEFT_OVER) is None


@pytest.mark.usefixtures("init_supporting_components")
async def test_never_configured(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test nothing is stored when debug recording was never configured."""
    await _async_setup(hass, None)

    assert STORAGE_KEY not in hass_storage
