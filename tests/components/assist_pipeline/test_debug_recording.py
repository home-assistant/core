"""Test cleaning up the Assist pipeline debug recordings."""

import os
from pathlib import Path
import time
from unittest.mock import patch

import pytest

from homeassistant.components.assist_pipeline.const import (
    CONF_DEBUG_RECORDING_DIR,
    DOMAIN,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

ISSUE_ID = "debug_recordings"
OLD_WAKE = Path("satellite", "Home Assistant", "1", "00_wake-wake_word.test.wav")
OLD_STT = Path("satellite", "Home Assistant", "1", "01_stt-stt.test.wav")
RECENT_STT = Path("Home Assistant", "2", "01_stt-stt.test.wav")
OTHER_FILE = Path("notes.txt")
OTHER_WAV = Path("sounds", "01_doorbell.wav")
EMPTY_DIR = Path("empty")
KEPT_FILES = [EMPTY_DIR, OTHER_FILE, OTHER_WAV.parent, OTHER_WAV]


def _write_recordings(recording_dir: Path) -> None:
    """Write recordings like the debug recording thread leaves behind."""
    for recording, days_old in ((OLD_WAKE, 31), (OLD_STT, 31), (RECENT_STT, 29)):
        path = recording_dir / recording
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0" * 500_000)
        modified = time.time() - days_old * 86400
        os.utime(path, (modified, modified))
    (recording_dir / OTHER_FILE).write_text("keep")
    (recording_dir / OTHER_WAV).parent.mkdir()
    (recording_dir / OTHER_WAV).write_bytes(b"keep")
    (recording_dir / EMPTY_DIR).mkdir()


def _delete_one_then_fail(recording_dir: Path, older_than: float | None = None) -> None:
    """Delete one recording, then fail like a file without write access."""
    (recording_dir / OLD_WAKE).unlink()
    raise PermissionError


def _list_files(recording_dir: Path) -> list[Path]:
    """Return the files and directories below the recording directory."""
    return sorted(path.relative_to(recording_dir) for path in recording_dir.rglob("*"))


@pytest.fixture
async def recording_dir(
    hass: HomeAssistant, init_supporting_components: None, tmp_path: Path
) -> Path:
    """Set up Assist pipeline with debug recordings on disk."""
    await hass.async_add_executor_job(_write_recordings, tmp_path)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_DEBUG_RECORDING_DIR: str(tmp_path)}}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return tmp_path


async def test_debug_recordings_repair(
    hass: HomeAssistant,
    recording_dir: Path,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue for kept debug recordings and deleting them."""
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "count": "3",
        "size": "1.5",
        "path": str(recording_dir),
    }

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert flow["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow["flow_id"])
    assert result["type"] == "create_entry"

    # Files that aren't recordings, and directories that weren't emptied, are kept.
    assert await hass.async_add_executor_job(_list_files, recording_dir) == KEPT_FILES
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_debug_recordings_repair_delete_failed(
    hass: HomeAssistant,
    recording_dir: Path,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix flow aborts when the recordings can't be deleted."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    with patch(
        "homeassistant.components.assist_pipeline.repairs.delete_debug_recordings",
        side_effect=_delete_one_then_fail,
    ):
        result = await process_repair_fix_flow(client, flow["flow_id"])

    assert result["type"] == "abort"
    assert result["reason"] == "delete_failed"
    # The issue shows the recordings that are left.
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_placeholders == {
        "count": "2",
        "size": "1.0",
        "path": str(recording_dir),
    }


async def test_no_debug_recordings(
    hass: HomeAssistant,
    init_supporting_components: None,
    tmp_path: Path,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test no issue is created for WAV files that aren't debug recordings."""
    await hass.async_add_executor_job((tmp_path / "01_doorbell.wav").write_bytes, b"")
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_DEBUG_RECORDING_DIR: str(tmp_path)}}
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_clear_debug_recordings(
    hass: HomeAssistant, recording_dir: Path, issue_registry: ir.IssueRegistry
) -> None:
    """Test clearing all debug recordings resolves the issue."""
    await hass.services.async_call(DOMAIN, "clear_debug_recordings", {}, blocking=True)

    assert await hass.async_add_executor_job(_list_files, recording_dir) == KEPT_FILES
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_clear_debug_recordings_older_than(
    hass: HomeAssistant, recording_dir: Path, issue_registry: ir.IssueRegistry
) -> None:
    """Test clearing old debug recordings updates the issue."""
    await hass.services.async_call(
        DOMAIN, "clear_debug_recordings", {"days": 30}, blocking=True
    )

    assert await hass.async_add_executor_job(_list_files, recording_dir) == sorted(
        [RECENT_STT.parent.parent, RECENT_STT.parent, RECENT_STT, *KEPT_FILES]
    )
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_placeholders == {
        "count": "1",
        "size": "0.5",
        "path": str(recording_dir),
    }


async def test_clear_debug_recordings_not_configured(
    hass: HomeAssistant, init_components: None
) -> None:
    """Test clearing fails without a debug recording directory."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN, "clear_debug_recordings", {}, blocking=True
        )

    assert exc_info.value.translation_key == "debug_recording_dir_not_configured"


async def test_clear_debug_recordings_delete_failed(
    hass: HomeAssistant, recording_dir: Path, issue_registry: ir.IssueRegistry
) -> None:
    """Test clearing fails when the recordings can't be deleted."""
    with (
        patch(
            "homeassistant.components.assist_pipeline.services.delete_debug_recordings",
            side_effect=_delete_one_then_fail,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN, "clear_debug_recordings", {}, blocking=True
        )

    assert exc_info.value.translation_key == "delete_debug_recordings_failed"
    # The issue shows the recordings that are left.
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_placeholders == {
        "count": "2",
        "size": "1.0",
        "path": str(recording_dir),
    }


async def test_clear_debug_recordings_requires_admin(
    hass: HomeAssistant, recording_dir: Path, hass_read_only_user: MockUser
) -> None:
    """Test only admins can clear the debug recordings."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "clear_debug_recordings",
            {},
            context=Context(user_id=hass_read_only_user.id),
            blocking=True,
        )

    assert await hass.async_add_executor_job(recording_dir.joinpath(OLD_STT).exists)
