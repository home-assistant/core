"""Test the recorder repairs."""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.recorder.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import (
    ClientSessionGenerator,
    RecorderInstanceContextManager,
    RecorderInstanceGenerator,
)

OLDER_CORRUPTION = "2026-01-01T00:00:00+00:00"
NEWER_CORRUPTION = "2026-02-01T00:00:00+00:00"
LATER_CORRUPTION = "2026-03-01T00:00:00+00:00"
ISSUE_ID = f"corrupt_database_files_{NEWER_CORRUPTION}"


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


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
    # A similar name that move_away_broken_database never writes must be kept.
    unrelated_file = db_file.with_name(f"other.db.corrupt.{NEWER_CORRUPTION}")
    await hass.async_add_executor_job(unrelated_file.write_bytes, b"keep")

    await async_setup_recorder_instance(hass)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "count": "4",
        "size": "2.0",
        "path": str(db_file.resolve().parent),
    }

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert flow["step_id"] == "confirm"
    # A corruption after the issue was shown must not be deleted with it.
    later_file = db_file.with_name(f"{db_file.name}.corrupt.{LATER_CORRUPTION}")
    await hass.async_add_executor_job(later_file.write_bytes, b"")

    result = await process_repair_fix_flow(client, flow["flow_id"])
    assert result["type"] == "create_entry"

    for corrupt_file in corrupt_files:
        assert not await hass.async_add_executor_job(corrupt_file.exists)
    assert await hass.async_add_executor_job(unrelated_file.exists)
    assert await hass.async_add_executor_job(later_file.exists)
    assert await hass.async_add_executor_job(db_file.exists)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


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
    await hass.async_add_executor_job(_write_corrupt_files, db_file)
    await async_setup_recorder_instance(hass)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    with patch(
        "homeassistant.components.recorder.repairs.delete_corrupt_database_files",
        side_effect=PermissionError,
    ):
        result = await process_repair_fix_flow(client, flow["flow_id"])

    assert result["type"] == "abort"
    assert result["reason"] == "delete_failed"
    assert "Could not delete the corrupt database files" in caplog.text
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.parametrize(
    ("corrupt_file_suffixes", "expected_issue_ids"),
    [
        pytest.param([], set(), id="no_files_left"),
        pytest.param(
            [f".corrupt.{NEWER_CORRUPTION}"],
            {ISSUE_ID},
            id="newer_corruption",
        ),
    ],
)
async def test_corrupt_database_files_issue_updated(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    issue_registry: ir.IssueRegistry,
    corrupt_file_suffixes: list[str],
    expected_issue_ids: set[str],
) -> None:
    """Test an older issue is replaced by a newer one or removed without files."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"corrupt_database_files_{OLDER_CORRUPTION}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="corrupt_database_files",
    )
    db_file = Path(recorder_db_url.removeprefix("sqlite:///"))
    for suffix in corrupt_file_suffixes:
        await hass.async_add_executor_job(
            db_file.with_name(f"{db_file.name}{suffix}").write_bytes, b""
        )

    await async_setup_recorder_instance(hass)
    await hass.async_block_till_done()

    assert {
        issue_id
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN and issue_id.startswith("corrupt_database_files_")
    } == expected_issue_ids
