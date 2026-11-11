"""Test the recorder repairs."""

from collections.abc import Iterable
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import (
    ClientSessionGenerator,
    RecorderInstanceContextManager,
    RecorderInstanceGenerator,
)

from homeassistant.components.recorder.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

OLDER_CORRUPTION = "2026-01-01T00:00:00+00:00"
NEWER_CORRUPTION = "2026-02-01T00:00:00+00:00"
LATER_CORRUPTION = "2026-03-01T00:00:00.123456+00:00"
CLOCK_BACK_CORRUPTION = "2025-12-01T00:00:00+00:00"
DIRECTORY_TIME = "2026-01-15T00:00:00+00:00"


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


def _issue_id(corrupt_files: list[Path]) -> str:
    """Return the issue ID for the given corrupt database files."""
    names = "/".join(sorted(file.name for file in corrupt_files))
    return f"corrupt_database_files_{hashlib.sha256(names.encode()).hexdigest()[:16]}"


def _write_corrupt_files(db_file: Path) -> list[Path]:
    """Write files like move_away_broken_database leaves behind."""
    corrupt_files = [
        db_file.with_name(f"{db_file.name}.corrupt.{OLDER_CORRUPTION}"),
        db_file.with_name(f"{db_file.name}.corrupt.{NEWER_CORRUPTION}"),
        db_file.with_name(f"{db_file.name}-wal.corrupt.{NEWER_CORRUPTION}"),
        db_file.with_name(f"{db_file.name}-shm.corrupt.{NEWER_CORRUPTION}"),
    ]
    for corrupt_file in corrupt_files:
        corrupt_file.write_bytes(b"\0" * 500_000)
    return corrupt_files


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
async def test_corrupt_database_files_repair(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue for kept corrupt database files and deleting them."""
    db_file = Path(recorder_db_url.removeprefix("sqlite:///"))
    corrupt_files = await hass.async_add_executor_job(_write_corrupt_files, db_file)
    # Names that move_away_broken_database never writes must be kept.
    unrelated_files = [
        db_file.with_name(f"other.db.corrupt.{NEWER_CORRUPTION}"),
        db_file.with_name(f"{db_file.name}.corrupt.manual-backup"),
    ]
    for unrelated_file in unrelated_files:
        await hass.async_add_executor_job(unrelated_file.write_bytes, b"keep")
    unrelated_dir = db_file.with_name(f"{db_file.name}.corrupt.{DIRECTORY_TIME}")
    await hass.async_add_executor_job(unrelated_dir.mkdir)

    await async_setup_recorder_instance(hass)
    await hass.async_block_till_done()

    issue_id = _issue_id(corrupt_files)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "count": "4",
        "size": "2.0",
        "path": str(db_file.resolve().parent),
    }

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert flow["step_id"] == "confirm"
    # Corruptions after the issue was shown must not be deleted with it,
    # even when the clock went back in between.
    later_files = [
        db_file.with_name(f"{db_file.name}.corrupt.{LATER_CORRUPTION}"),
        db_file.with_name(f"{db_file.name}-wal.corrupt.{CLOCK_BACK_CORRUPTION}"),
    ]
    for later_file in later_files:
        await hass.async_add_executor_job(later_file.write_bytes, b"")

    result = await process_repair_fix_flow(client, flow["flow_id"])
    assert result["type"] == "create_entry"

    for corrupt_file in corrupt_files:
        assert not await hass.async_add_executor_job(corrupt_file.exists)
    for kept_path in (*unrelated_files, unrelated_dir, *later_files):
        assert await hass.async_add_executor_job(kept_path.exists)
    assert await hass.async_add_executor_job(db_file.exists)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
async def test_corrupt_database_files_delete_failed(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the fix flow aborts when the files can't be deleted."""
    db_file = Path(recorder_db_url.removeprefix("sqlite:///"))
    corrupt_files = await hass.async_add_executor_job(_write_corrupt_files, db_file)
    await async_setup_recorder_instance(hass)
    await hass.async_block_till_done()

    issue_id = _issue_id(corrupt_files)
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, issue_id)
    with patch(
        "homeassistant.components.recorder.repairs.delete_corrupt_database_files",
        side_effect=PermissionError,
    ):
        result = await process_repair_fix_flow(client, flow["flow_id"])

    assert result["type"] == "abort"
    assert result["reason"] == "delete_failed"
    assert "Could not delete the corrupt database files" in caplog.text
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.parametrize(
    ("corrupt_file_times", "expected_issue_times"),
    [
        pytest.param([], set(), id="no_files_left"),
        pytest.param(
            [OLDER_CORRUPTION],
            {((OLDER_CORRUPTION,), True)},
            id="same_files_stay_ignored",
        ),
        pytest.param(
            [NEWER_CORRUPTION],
            {((NEWER_CORRUPTION,), False)},
            id="newer_corruption",
        ),
        pytest.param(
            [OLDER_CORRUPTION, CLOCK_BACK_CORRUPTION],
            {((OLDER_CORRUPTION, CLOCK_BACK_CORRUPTION), False)},
            id="earlier_timestamp_after_clock_went_back",
        ),
    ],
)
async def test_corrupt_database_files_issue_updated(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    issue_registry: ir.IssueRegistry,
    corrupt_file_times: list[str],
    expected_issue_times: set[tuple[tuple[str, ...], bool]],
) -> None:
    """Test an ignored issue only hides the files it was created for."""
    db_file = Path(recorder_db_url.removeprefix("sqlite:///"))

    def corrupt_files(times: Iterable[str]) -> list[Path]:
        return [db_file.with_name(f"{db_file.name}.corrupt.{time}") for time in times]

    ignored_issue_id = _issue_id(corrupt_files([OLDER_CORRUPTION]))
    ir.async_create_issue(
        hass,
        DOMAIN,
        ignored_issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="corrupt_database_files",
    )
    ir.async_ignore_issue(hass, DOMAIN, ignored_issue_id, True)
    for corrupt_file in corrupt_files(corrupt_file_times):
        await hass.async_add_executor_job(corrupt_file.write_bytes, b"")

    await async_setup_recorder_instance(hass)
    await hass.async_block_till_done()

    assert {
        (issue_id, issue.dismissed_version is not None)
        for (domain, issue_id), issue in issue_registry.issues.items()
        if domain == DOMAIN and issue_id.startswith("corrupt_database_files_")
    } == {
        (_issue_id(corrupt_files(times)), ignored)
        for times, ignored in expected_issue_times
    }


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
async def test_corrupt_database_files_scan_failed(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the recorder starts and keeps the issue when the scan fails."""
    db_file = Path(recorder_db_url.removeprefix("sqlite:///"))
    corrupt_files = await hass.async_add_executor_job(_write_corrupt_files, db_file)
    issue_id = _issue_id(corrupt_files)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="corrupt_database_files",
    )

    with patch(
        "homeassistant.components.recorder.core.find_corrupt_database_files",
        side_effect=PermissionError,
    ):
        instance = await async_setup_recorder_instance(hass)
        await hass.async_block_till_done()

    assert instance.engine is not None
    assert "Could not look for corrupt database files" in caplog.text
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
