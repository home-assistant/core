"""Tests for the Span Panel coordinator."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from span_panel_api.exceptions import (
    SpanPanelAPIError,
    SpanPanelAuthError,
    SpanPanelConnectionError,
    SpanPanelServerError,
    SpanPanelTimeoutError,
)

from homeassistant.components.span_panel.coordinator import SpanPanelCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .factories import (
    SpanBatterySnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
)

from tests.common import MockConfigEntry


def _create_coordinator(
    hass: HomeAssistant,
    *,
    client: MagicMock | None = None,
    options: dict | None = None,
) -> SpanPanelCoordinator:
    """Create a coordinator with mocked dependencies."""
    return SpanPanelCoordinator(
        hass,
        client or MagicMock(),
        MockConfigEntry(
            domain="span_panel",
            options=options or {},
            entry_id="entry-123",
            title="SPAN Panel",
        ),
    )


async def test_capability_change_requests_reload(hass: HomeAssistant) -> None:
    """A new hardware capability should trigger a reload request."""
    coordinator = _create_coordinator(hass)

    baseline = SpanPanelSnapshotFactory.create()
    upgraded = SpanPanelSnapshotFactory.create(
        battery=SpanBatterySnapshotFactory.create(soe_percentage=88.0),
        power_flow_pv=1250.0,
        power_flow_site=3000.0,
        evse={"evse-0": SpanEvseSnapshotFactory.create()},
    )

    coordinator._check_capability_change(baseline)
    assert coordinator._known_capabilities == frozenset()
    assert coordinator._reload_requested is False

    coordinator._check_capability_change(upgraded)

    assert coordinator._known_capabilities == frozenset(
        {"bess", "evse", "power_flows", "pv"}
    )
    assert coordinator._reload_requested is True


async def test_async_update_data_returns_cached_snapshot_on_connection_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A transient connection error should return cached data when available."""
    client = MagicMock()
    client.get_snapshot = AsyncMock(
        side_effect=SpanPanelConnectionError("panel offline")
    )
    coordinator = _create_coordinator(hass, client=client)
    cached_snapshot = SpanPanelSnapshotFactory.create(serial_number="sp3-cached-001")
    coordinator.data = cached_snapshot

    caplog.set_level(logging.INFO)

    result = await coordinator._async_update_data()

    assert result is cached_snapshot
    assert coordinator.panel_offline is True
    assert "SPAN Panel is unavailable: panel offline" in caplog.text


async def test_async_update_data_raises_auth_failed(hass: HomeAssistant) -> None:
    """Authentication failures should be promoted to config-entry auth errors."""
    client = MagicMock()
    client.get_snapshot = AsyncMock(side_effect=SpanPanelAuthError("bad auth"))
    coordinator = _create_coordinator(hass, client=client)

    with pytest.raises(Exception) as err:
        await coordinator._async_update_data()

    assert err.type.__name__ == "ConfigEntryAuthFailed"


async def test_run_post_update_tasks_validates_once_and_schedules_reload(
    hass: HomeAssistant,
) -> None:
    """Post-update tasks should validate once and schedule a requested reload."""
    coordinator = _create_coordinator(hass)
    snapshot = SpanPanelSnapshotFactory.create()
    coordinator._reload_requested = True

    with (
        patch.object(coordinator, "_run_schema_validation") as mock_validate,
        patch.object(coordinator, "_fire_dip_notification", AsyncMock()) as mock_notify,
        patch.object(coordinator, "_async_reload_task", AsyncMock()) as mock_reload,
        patch.object(hass, "async_create_task") as mock_create_task,
    ):
        await coordinator._run_post_update_tasks(snapshot)
        await coordinator._run_post_update_tasks(snapshot)

    assert mock_validate.call_count == 1
    assert mock_notify.await_count == 2
    assert mock_create_task.call_count == 1
    reload_coro = mock_create_task.call_args.args[0]
    reload_coro.close()
    mock_reload.assert_called_once()
    assert coordinator._reload_requested is False


async def test_async_shutdown_unregisters_streaming_and_closes_client(
    hass: HomeAssistant,
) -> None:
    """Shutdown should unregister streaming and close the client."""
    client = MagicMock()
    client.stop_streaming = AsyncMock()
    client.close = AsyncMock()
    unregister = MagicMock()
    coordinator = _create_coordinator(hass, client=client)
    coordinator._unregister_streaming = unregister

    await coordinator.async_shutdown()

    unregister.assert_called_once()
    client.stop_streaming.assert_awaited_once()
    client.close.assert_awaited_once()
    assert coordinator._unregister_streaming is None


async def test_report_dip_and_fire_notification_clears_events(
    hass: HomeAssistant,
) -> None:
    """Dip notifications should summarize and clear pending events."""
    coordinator = _create_coordinator(hass)
    coordinator.report_energy_dip("sensor.a", 2.5, 4.0)
    coordinator.report_energy_dip("sensor.b", 1.0, 1.5)

    with patch(
        "homeassistant.components.span_panel.coordinator.async_create"
    ) as mock_create:
        await coordinator._fire_dip_notification()

    mock_create.assert_called_once()
    body = mock_create.call_args.args[1]
    assert "sensor.a" in body
    assert "dip 2.5 Wh" in body
    assert coordinator._pending_dip_events == []


async def test_fire_dip_notification_noops_without_events(hass: HomeAssistant) -> None:
    """No notification should be created when there are no pending dips."""
    coordinator = _create_coordinator(hass)

    with patch(
        "homeassistant.components.span_panel.coordinator.async_create"
    ) as mock_create:
        await coordinator._fire_dip_notification()

    mock_create.assert_not_called()


async def test_async_setup_streaming_registers_callback_and_starts_client(
    hass: HomeAssistant,
) -> None:
    """Streaming setup should register the callback and start the client."""
    client = MagicMock()
    client.register_snapshot_callback = MagicMock(return_value=MagicMock())
    client.start_streaming = AsyncMock()
    coordinator = _create_coordinator(hass, client=client)

    await coordinator.async_setup_streaming()

    client.register_snapshot_callback.assert_called_once()
    client.start_streaming.assert_awaited_once()
    assert coordinator._unregister_streaming is not None


async def test_on_snapshot_push_updates_state_and_runs_post_tasks(
    hass: HomeAssistant,
) -> None:
    """Push snapshots should update coordinator data and run maintenance."""
    coordinator = _create_coordinator(hass)
    coordinator._panel_offline = True
    snapshot = SpanPanelSnapshotFactory.create()

    with (
        patch.object(coordinator, "_check_capability_change") as mock_caps,
        patch.object(coordinator, "async_set_updated_data") as mock_set,
        patch.object(coordinator, "_run_post_update_tasks", AsyncMock()) as mock_post,
    ):
        await coordinator._on_snapshot_push(snapshot)

    assert coordinator.panel_offline is False
    mock_caps.assert_called_once_with(snapshot)
    mock_set.assert_called_once_with(snapshot)
    mock_post.assert_awaited_once_with(snapshot)


async def test_run_schema_validation_skips_without_metadata(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Schema validation should skip cleanly when no metadata is available."""

    class FakeSpanMqttClient:
        field_metadata = None

    client = FakeSpanMqttClient()
    coordinator = _create_coordinator(hass, client=client)

    caplog.set_level(logging.DEBUG)

    with patch(
        "homeassistant.components.span_panel.coordinator.SpanMqttClient",
        FakeSpanMqttClient,
    ):
        coordinator._run_schema_validation()

    assert "Schema validation skipped" in caplog.text


async def test_run_schema_validation_validates_field_metadata(
    hass: HomeAssistant,
) -> None:
    """Schema validation should pass field metadata to the validator."""

    class FakeField:
        def __init__(self, unit: str, datatype: str) -> None:
            self.unit = unit
            self.datatype = datatype

    class FakeSpanMqttClient:
        field_metadata = {"instantPowerW": FakeField("W", "number")}

    client = FakeSpanMqttClient()
    coordinator = _create_coordinator(hass, client=client)

    with (
        patch(
            "homeassistant.components.span_panel.coordinator.SpanMqttClient",
            FakeSpanMqttClient,
        ),
        patch(
            "homeassistant.components.span_panel.coordinator.collect_sensor_definitions",
            return_value={"sensor_defs": "ok"},
        ) as mock_collect,
        patch(
            "homeassistant.components.span_panel.coordinator.validate_field_metadata"
        ) as mock_validate,
    ):
        coordinator._run_schema_validation()

    mock_collect.assert_called_once()
    mock_validate.assert_called_once_with(
        {"instantPowerW": {"unit": "W", "datatype": "number"}},
        sensor_defs={"sensor_defs": "ok"},
    )


@pytest.mark.parametrize(
    ("error", "expected_log"),
    [
        (SpanPanelTimeoutError("timeout"), "SPAN Panel is unavailable: timeout"),
        (SpanPanelServerError("server"), "SPAN Panel is unavailable: server"),
        (SpanPanelAPIError("api"), "SPAN Panel is unavailable: api"),
        (RuntimeError("boom"), "SPAN Panel is unavailable: boom"),
    ],
)
async def test_async_update_data_raises_first_error_without_cached_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    expected_log: str,
) -> None:
    """First-refresh errors should be re-raised after logging."""
    client = MagicMock()
    client.get_snapshot = AsyncMock(side_effect=error)
    coordinator = _create_coordinator(hass, client=client)

    caplog.set_level(logging.INFO)

    with pytest.raises(type(error)):
        await coordinator._async_update_data()

    assert coordinator.panel_offline is True
    assert expected_log in caplog.text


async def test_async_update_data_re_raises_existing_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Existing auth failures should pass through untouched."""
    client = MagicMock()
    client.get_snapshot = AsyncMock(side_effect=ConfigEntryAuthFailed)
    coordinator = _create_coordinator(hass, client=client)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_async_update_data_logs_unavailable_and_recovery_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Coordinator should log offline and recovery transitions once each."""
    cached_snapshot = SpanPanelSnapshotFactory.create(serial_number="sp3-cached-001")
    recovered_snapshot = SpanPanelSnapshotFactory.create(
        serial_number="sp3-recovered-001"
    )
    client = MagicMock()
    client.get_snapshot = AsyncMock(
        side_effect=[
            SpanPanelConnectionError("panel offline"),
            SpanPanelConnectionError("still offline"),
            recovered_snapshot,
        ]
    )
    coordinator = _create_coordinator(hass, client=client)
    coordinator.data = cached_snapshot

    caplog.set_level(logging.INFO)

    assert await coordinator._async_update_data() is cached_snapshot
    assert await coordinator._async_update_data() is cached_snapshot
    assert await coordinator._async_update_data() is recovered_snapshot

    assert caplog.text.count("SPAN Panel is unavailable: panel offline") == 1
    assert "SPAN Panel is unavailable: still offline" not in caplog.text
    assert caplog.text.count("SPAN Panel is back online") == 1


async def test_async_reload_task_handles_expected_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Reload task should log and suppress reload-related errors."""
    coordinator = _create_coordinator(hass)

    caplog.set_level(logging.WARNING)

    with (
        patch.object(hass, "async_block_till_done", AsyncMock()),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(side_effect=ConfigEntryNotReady("not ready")),
        ),
    ):
        await coordinator._async_reload_task()

    assert "Config entry not ready during reload: not ready" in caplog.text

    caplog.clear()
    caplog.set_level(logging.ERROR)

    with (
        patch.object(hass, "async_block_till_done", AsyncMock()),
        patch.object(
            hass.config_entries,
            "async_reload",
            AsyncMock(side_effect=HomeAssistantError("reload failed")),
        ),
    ):
        await coordinator._async_reload_task()

    assert "Home Assistant error during reload: reload failed" in caplog.text
