"""Unit tests for repairs.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.truenas_ce.const import MIGRATION_RECORDS
from homeassistant.components.truenas_ce.repairs import (
    MigrationRollbackRepairFlow,
    _async_rollback_and_log_errors,
    async_create_fix_flow,
)


def _close_coroutine(coro: object) -> None:
    """Close an unused coroutine so pytest doesn't warn about it never being awaited."""
    if hasattr(coro, "close"):
        coro.close()


def _make_hass(entry: SimpleNamespace | None) -> SimpleNamespace:
    return SimpleNamespace(
        config_entries=SimpleNamespace(
            async_get_entry=MagicMock(return_value=entry),
            async_update_entry=MagicMock(),
        ),
        async_create_task=MagicMock(side_effect=_close_coroutine),
    )


async def test_create_fix_flow_routes_migration_rollback_issue() -> None:
    """A ``migration_rollback_available_*`` issue id routes to the migration-rollback flow."""
    flow = await async_create_fix_flow(
        SimpleNamespace(), "migration_rollback_available_entry2", None
    )
    assert isinstance(flow, MigrationRollbackRepairFlow)

    # Confirm the entry id was parsed out correctly by observing which entry
    # the flow acts on, rather than reading the private ``_entry_id`` field.
    flow.hass = _make_hass(SimpleNamespace(data={}))
    await flow.async_step_init()
    flow.hass.config_entries.async_get_entry.assert_called_once_with("entry2")


async def test_create_fix_flow_raises_on_unknown_issue_id() -> None:
    """An unrecognized issue id raises instead of being silently misrouted."""
    with pytest.raises(ValueError, match="Unknown TrueNAS repair issue id"):
        await async_create_fix_flow(SimpleNamespace(), "some_other_issue_entry3", None)


async def test_migration_rollback_init_counts_adopted_entities() -> None:
    """The init step reports how many entities ``MIGRATION_RECORDS`` lists as adopted."""
    entry = SimpleNamespace(data={MIGRATION_RECORDS: ["a", "b", "c"]})
    flow = MigrationRollbackRepairFlow("entry2")
    flow.hass = _make_hass(entry)

    result = await flow.async_step_init()
    assert result["description_placeholders"] == {"count": "3"}


async def test_migration_rollback_init_no_entry_zero_count() -> None:
    """With no config entry, the init step reports a zero adopted-entity count."""
    flow = MigrationRollbackRepairFlow("entry2")
    flow.hass = _make_hass(None)

    result = await flow.async_step_init()
    assert result["description_placeholders"] == {"count": "0"}


async def test_migration_rollback_step_schedules_rollback_task() -> None:
    """Rolling back schedules the rollback task and deletes the issue."""
    entry = SimpleNamespace(data={})
    flow = MigrationRollbackRepairFlow("entry2")
    flow.hass = _make_hass(entry)

    with (
        patch(
            "homeassistant.components.truenas_ce.repairs.ir.async_delete_issue"
        ) as delete_issue,
        patch(
            "homeassistant.components.truenas_ce.repairs.async_rollback_to_legacy",
            new=AsyncMock(),
        ),
    ):
        result = await flow.async_step_rollback()

    flow.hass.async_create_task.assert_called_once()
    delete_issue.assert_called_once()
    assert result["type"] == "create_entry"


async def test_migration_rollback_step_no_entry_skips_task() -> None:
    """With no config entry, the rollback step deletes the issue but schedules no task."""
    flow = MigrationRollbackRepairFlow("entry2")
    flow.hass = _make_hass(None)

    with patch(
        "homeassistant.components.truenas_ce.repairs.ir.async_delete_issue"
    ) as delete_issue:
        await flow.async_step_rollback()

    flow.hass.async_create_task.assert_not_called()
    delete_issue.assert_called_once()


async def test_migration_rollback_ignore_deletes_issue() -> None:
    """Ignoring the migration-rollback issue deletes it and finishes the flow."""
    flow = MigrationRollbackRepairFlow("entry2")
    flow.hass = _make_hass(None)

    with patch(
        "homeassistant.components.truenas_ce.repairs.ir.async_delete_issue"
    ) as delete_issue:
        result = await flow.async_step_ignore()

    delete_issue.assert_called_once()
    assert result["type"] == "create_entry"


async def test_rollback_task_success_raises_no_failure_issue() -> None:
    """The success path must not touch the issue registry at all."""
    hass = SimpleNamespace()
    entry = SimpleNamespace(entry_id="entry2", title="TrueNAS")

    with (
        patch(
            "homeassistant.components.truenas_ce.repairs.async_rollback_to_legacy",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.truenas_ce.repairs.ir.async_create_issue"
        ) as create_issue,
    ):
        await _async_rollback_and_log_errors(hass, entry)

    create_issue.assert_not_called()


async def test_rollback_task_false_result_raises_visible_issue() -> None:
    """A ``False`` result (nothing torn down) must surface just like a crash.

    ``async_rollback_to_legacy`` returns ``False`` without raising when there
    is nothing to roll back or the legacy entry failed to set up; since the
    ``migration_rollback_available`` issue is already deleted by the caller,
    a silent ``False`` would otherwise leave the user with no feedback at all.
    """
    hass = SimpleNamespace()
    entry = SimpleNamespace(entry_id="entry2", title="TrueNAS")

    with (
        patch(
            "homeassistant.components.truenas_ce.repairs.async_rollback_to_legacy",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "homeassistant.components.truenas_ce.repairs.ir.async_create_issue"
        ) as create_issue,
    ):
        await _async_rollback_and_log_errors(hass, entry)

    create_issue.assert_called_once()
    _, args, kwargs = create_issue.mock_calls[0]
    assert args == (hass, "truenas_ce", "migration_rollback_failed_entry2")
    assert kwargs["is_fixable"] is False
    assert kwargs["translation_key"] == "migration_rollback_failed"
    assert kwargs["translation_placeholders"] == {"name": "TrueNAS"}


async def test_rollback_task_failure_raises_visible_issue() -> None:
    """A failed background rollback must surface as its own Repairs issue.

    The original migration_rollback_available issue is already deleted by
    the caller before this task can finish (see
    MigrationRollbackRepairFlow.async_step_rollback), so this is the only
    remaining UI-visible signal that the rollback didn't actually happen.
    """
    hass = SimpleNamespace()
    entry = SimpleNamespace(entry_id="entry2", title="TrueNAS")

    with (
        patch(
            "homeassistant.components.truenas_ce.repairs.async_rollback_to_legacy",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "homeassistant.components.truenas_ce.repairs.ir.async_create_issue"
        ) as create_issue,
    ):
        await _async_rollback_and_log_errors(hass, entry)

    create_issue.assert_called_once()
    _, args, kwargs = create_issue.mock_calls[0]
    assert args == (hass, "truenas_ce", "migration_rollback_failed_entry2")
    assert kwargs["is_fixable"] is False
    assert kwargs["translation_key"] == "migration_rollback_failed"
    assert kwargs["translation_placeholders"] == {"name": "TrueNAS"}
