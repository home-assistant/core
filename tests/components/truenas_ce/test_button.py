"""Unit tests for button.py."""

from __future__ import annotations

import pytest

from homeassistant.components.truenas_ce.button import (
    TrueNASButton,
    TrueNASMigrationRollbackButton,
    TrueNASPoolScrubButton,
    TrueNASRefreshButton,
    TrueNASStatisticsCleanupButton,
)
from homeassistant.components.truenas_ce.button_types import (
    TrueNASButtonEntityDescription,
)
from homeassistant.components.truenas_ce.const import DOMAIN, MIGRATION_LEGACY_ENTRY_ID
from homeassistant.exceptions import HomeAssistantError

from ._fakes import make_coordinator

_RUN_DESC = TrueNASButtonEntityDescription(
    key="rsynctask_run", name="Run", data_path="rsynctask", api_method="rsynctask.run"
)


def _make_button(*, data: dict | None = None, description=None) -> TrueNASButton:
    coordinator = make_coordinator(data={"rsynctask": {"t1": (data or {})}})
    return TrueNASButton(coordinator, description or _RUN_DESC, "t1")


async def test_async_press_missing_method_logs_and_skips() -> None:
    desc = TrueNASButtonEntityDescription(
        key="k", name="Run", data_path="rsynctask", api_method=None
    )
    button = _make_button(data={"id": 1}, description=desc)
    await button.async_press()
    button.coordinator.async_run_task.assert_not_awaited()


async def test_async_press_missing_object_id_logs_and_skips() -> None:
    button = _make_button(data={})
    await button.async_press()
    button.coordinator.async_run_task.assert_not_awaited()


async def test_async_press_triggers_run_task() -> None:
    button = _make_button(data={"id": 7})
    await button.async_press()
    button.coordinator.async_run_task.assert_awaited_once_with(
        "rsynctask.run", 7, "rsynctask"
    )


def _make_scrub_button(*, data: dict | None = None) -> TrueNASPoolScrubButton:
    desc = TrueNASButtonEntityDescription(
        key="scrub_run", name="Run", data_path="snapshottask"
    )
    coordinator = make_coordinator(data={"snapshottask": {"t1": (data or {})}})
    return TrueNASPoolScrubButton(coordinator, desc, "t1")


async def test_scrub_button_missing_pool_name_skips() -> None:
    button = _make_scrub_button(data={"id": 1, "enabled": True})
    await button.async_press()
    button.coordinator.api.query.assert_not_awaited()


async def test_scrub_button_disabled_skips() -> None:
    button = _make_scrub_button(data={"pool_name": "tank", "id": 1, "enabled": False})
    await button.async_press()
    button.coordinator.api.query.assert_not_awaited()


async def test_scrub_button_success_sets_optimistic_running() -> None:
    button = _make_scrub_button(data={"pool_name": "tank", "id": 5, "enabled": True})
    button.coordinator.api.query.return_value = 123
    await button.async_press()
    button.coordinator.api.query.assert_awaited_once_with(
        "pool.scrub.scrub", ["tank", "START"]
    )
    button.coordinator.set_optimistic_running.assert_called_once_with("snapshottask", 5)


async def test_scrub_button_failure_raises() -> None:
    button = _make_scrub_button(data={"pool_name": "tank", "id": 5, "enabled": True})
    button.coordinator.api.query.return_value = None
    button.coordinator.api.error = "middleware down"
    with pytest.raises(HomeAssistantError) as exc_info:
        await button.async_press()
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "scrub_failed"
    assert exc_info.value.translation_placeholders == {
        "pool": "tank",
        "host": button.coordinator.host,
        "error": "middleware down",
    }


def test_statistics_cleanup_button_init_and_available() -> None:
    coordinator = make_coordinator()
    button = TrueNASStatisticsCleanupButton(coordinator)
    assert button.unique_id == "truenas-statistics_cleanup"
    assert button.available is False
    coordinator.orphaned_statistics = ["sensor.truenas_old"]
    assert button.available is True


async def test_statistics_cleanup_button_press_clears_statistics() -> None:
    coordinator = make_coordinator()
    button = TrueNASStatisticsCleanupButton(coordinator)
    await button.async_press()
    coordinator.async_clear_orphaned_statistics.assert_awaited_once()


def test_migration_rollback_button_available_false_without_legacy_id() -> None:
    coordinator = make_coordinator()
    button = TrueNASMigrationRollbackButton(coordinator)
    button.hass = coordinator.hass
    assert button.available is False


def test_migration_rollback_button_available_true_when_legacy_entry_exists() -> None:
    coordinator = make_coordinator(data={}, config_entry=None)
    coordinator.config_entry.data[MIGRATION_LEGACY_ENTRY_ID] = "legacy-1"
    coordinator.hass.config_entries.async_get_entry.return_value = object()
    button = TrueNASMigrationRollbackButton(coordinator)
    button.hass = coordinator.hass
    assert button.available is True


async def test_migration_rollback_button_press_raises_issue() -> None:
    coordinator = make_coordinator()
    button = TrueNASMigrationRollbackButton(coordinator)
    await button.async_press()
    coordinator.raise_migration_rollback_issue.assert_called_once()


async def test_refresh_button_press_refreshes_coordinator() -> None:
    coordinator = make_coordinator()
    button = TrueNASRefreshButton(coordinator)
    await button.async_press()
    coordinator.async_refresh.assert_awaited_once()
