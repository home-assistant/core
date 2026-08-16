"""Unit tests for repairs.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.truenas_ce.const import MIGRATION_RECORDS
from homeassistant.components.truenas_ce.repairs import (
    MigrationRollbackRepairFlow,
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
    assert flow._entry_id == "entry2"


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
