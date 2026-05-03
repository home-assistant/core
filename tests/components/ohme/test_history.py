"""Tests for Ohme energy history sync behavior."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from ohme import ChargerStatus
import pytest

from homeassistant.components.ohme.const import CONF_BACKFILL_DAYS
from homeassistant.components.ohme.history import (
    ImportedStatisticsState,
    async_ensure_energy_history,
    async_remove_energy_history,
    async_sync_energy_history_window,
    history_window_start,
    repair_window_start,
    statistic_id_from_serial,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


def _to_ms(timestamp: datetime) -> int:
    """Convert a datetime to milliseconds since the Unix epoch."""
    return int(timestamp.timestamp() * 1000)


def _summary_side_effect(total_wh: int) -> AsyncMock:
    """Build a mocked summary endpoint for one day of hourly charging."""
    day_start = datetime(2026, 4, 5, tzinfo=dt_util.UTC)
    month_points = [(day_start, total_wh)]
    hourly_points = [
        (datetime(2026, 4, 5, 3, tzinfo=dt_util.UTC), 2.0),
        (datetime(2026, 4, 5, 4, tzinfo=dt_util.UTC), 3.5),
    ]

    async def _mock_summary(
        *, start_ts: int, end_ts: int, granularity: str
    ) -> dict[str, object]:
        granularity_name = getattr(granularity, "value", granularity)

        if granularity_name == "MONTH":
            return {
                "totalStats": {"energyChargedTotalWh": total_wh},
                "stats": [
                    {
                        "startTime": _to_ms(bucket_start),
                        "endTime": _to_ms(bucket_start + timedelta(days=30)),
                        "energyChargedTotalWh": bucket_wh,
                    }
                    for bucket_start, bucket_wh in month_points
                    if start_ts <= _to_ms(bucket_start) < end_ts
                ],
            }

        if granularity_name == "DAY":
            return {"totalStats": {"energyChargedTotalWh": total_wh}, "stats": []}

        if granularity_name == "HOUR":
            return {
                "totalStats": {"energyChargedTotalWh": total_wh},
                "stats": [
                    {
                        "startTime": _to_ms(bucket_start),
                        "endTime": _to_ms(bucket_start + timedelta(hours=1)),
                        "energyChargedTotalWh": int(bucket_kwh * 1000),
                    }
                    for bucket_start, bucket_kwh in hourly_points
                    if start_ts <= _to_ms(bucket_start) < end_ts
                ],
            }

        raise AssertionError(f"Unexpected granularity {granularity}")

    return AsyncMock(side_effect=_mock_summary)


def _make_charge_session_side_effect(
    mock_client: MagicMock,
    updates: list[dict[str, object]],
) -> AsyncMock:
    """Build a charge-session side effect that mutates the mocked client."""
    index = 0

    async def _side_effect() -> None:
        nonlocal index
        payload = updates[min(index, len(updates) - 1)]
        index += 1
        mock_client.status = payload["status"]
        mock_client.session_start = payload.get("session_start")
        mock_client.session_finish = payload.get("session_finish")

    return AsyncMock(side_effect=_side_effect)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_bootstraps_total_charged_energy_statistics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setup bootstraps external statistics for total charged energy."""
    mock_client.async_get_charge_summary = _summary_side_effect(total_wh=5500)

    with (
        patch(
            "homeassistant.components.ohme.history.async_get_imported_statistics_state",
            new=AsyncMock(return_value=ImportedStatisticsState()),
        ),
        patch(
            "homeassistant.components.ohme.history.async_save_sync_state",
            new=AsyncMock(),
        ) as mock_save_state,
        patch(
            "homeassistant.components.ohme.history.async_add_external_statistics"
        ) as mock_add_statistics,
    ):
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry,
            options={CONF_BACKFILL_DAYS: 0},
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_add_statistics.assert_called_once()
    metadata = mock_add_statistics.call_args.args[1]
    rows = mock_add_statistics.call_args.args[2]

    assert metadata["statistic_id"].startswith("ohme:total_charged_energy_")
    assert len(rows) == 3
    assert rows[0]["sum"] == 0.0
    assert rows[1]["state"] == 2.0
    assert rows[2]["sum"] == 5.5

    mock_save_state.assert_awaited_once_with(hass, mock_config_entry)


async def test_remove_energy_history_uses_entry_unique_id_when_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test history cleanup can derive the statistic id without runtime data."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id="chargerid")

    with (
        patch(
            "homeassistant.components.ohme.history.async_clear_statistics",
            new=AsyncMock(),
        ) as mock_clear_statistics,
        patch(
            "homeassistant.components.ohme.history.async_remove_sync_state",
            new=AsyncMock(),
        ) as mock_remove_sync_state,
    ):
        await async_remove_energy_history(hass, mock_config_entry)

    mock_clear_statistics.assert_awaited_once_with(
        hass, statistic_id_from_serial("chargerid")
    )
    mock_remove_sync_state.assert_awaited_once_with(hass, mock_config_entry)


async def test_ensure_energy_history_recovers_from_last_imported_hour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test startup recovery sync starts from the last imported hour overlap."""
    runtime_data = MagicMock()
    runtime_data.charge_session_coordinator.client = mock_client
    mock_config_entry.runtime_data = runtime_data

    last_start = datetime(2026, 4, 5, 10, tzinfo=dt_util.UTC)
    imported_state = ImportedStatisticsState(
        last_start=last_start,
        last_sum_kwh=12.345,
    )

    with (
        patch(
            "homeassistant.components.ohme.history.async_get_imported_statistics_state",
            new=AsyncMock(return_value=imported_state),
        ),
        patch(
            "homeassistant.components.ohme.history.async_load_sync_state",
            new=AsyncMock(return_value={CONF_BACKFILL_DAYS: 365}),
        ),
        patch(
            "homeassistant.components.ohme.history.async_sync_energy_history_window",
            new=AsyncMock(return_value={"action": "window_sync"}),
        ) as mock_sync,
    ):
        await async_ensure_energy_history(hass, mock_config_entry)

    mock_sync.assert_awaited_once_with(
        hass,
        mock_config_entry,
        window_start=max(
            history_window_start(mock_config_entry),
            last_start - timedelta(hours=1),
        ),
        reason="startup_recovery",
    )


async def test_ensure_energy_history_rebuilds_if_backfill_days_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test changing backfill days still forces a full rebuild."""
    runtime_data = MagicMock()
    runtime_data.charge_session_coordinator.client = mock_client
    mock_config_entry.runtime_data = runtime_data

    imported_state = ImportedStatisticsState(
        last_start=datetime(2026, 4, 5, 10, tzinfo=dt_util.UTC),
        last_sum_kwh=12.345,
    )

    with (
        patch(
            "homeassistant.components.ohme.history.async_get_imported_statistics_state",
            new=AsyncMock(return_value=imported_state),
        ),
        patch(
            "homeassistant.components.ohme.history.async_load_sync_state",
            new=AsyncMock(return_value={CONF_BACKFILL_DAYS: 30}),
        ),
        patch(
            "homeassistant.components.ohme.history.async_full_rebuild_energy_history",
            new=AsyncMock(return_value={"action": "full_rebuild"}),
        ) as mock_full_rebuild,
    ):
        await async_ensure_energy_history(hass, mock_config_entry)

    mock_full_rebuild.assert_awaited_once_with(
        hass,
        mock_config_entry,
        reason="backfill_days_changed",
    )


async def test_full_rebuild_does_not_clear_existing_statistics_before_refetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a failed rebuild leaves existing imported statistics untouched."""
    runtime_data = MagicMock()
    runtime_data.charge_session_coordinator.client = mock_client
    mock_config_entry.runtime_data = runtime_data

    imported_state = ImportedStatisticsState(
        last_start=datetime(2026, 4, 5, 10, tzinfo=dt_util.UTC),
        last_sum_kwh=12.345,
    )

    with (
        patch(
            "homeassistant.components.ohme.history.async_get_imported_statistics_state",
            new=AsyncMock(return_value=imported_state),
        ),
        patch(
            "homeassistant.components.ohme.history.async_get_total_before_window",
            new=AsyncMock(return_value=5.0),
        ),
        patch(
            "homeassistant.components.ohme.history.async_fetch_hourly_energy_points",
            new=AsyncMock(side_effect=RuntimeError("summary fetch failed")),
        ),
        patch(
            "homeassistant.components.ohme.history.async_clear_statistics",
            new=AsyncMock(),
        ) as mock_clear_statistics,
        patch(
            "homeassistant.components.ohme.history.async_add_external_statistics"
        ) as mock_add_statistics,
        pytest.raises(RuntimeError, match="summary fetch failed"),
    ):
        await async_sync_energy_history_window(
            hass,
            mock_config_entry,
            window_start=history_window_start(mock_config_entry),
            reason="test_failed_rebuild",
            full_rebuild=True,
        )

    mock_clear_statistics.assert_not_awaited()
    mock_add_statistics.assert_not_called()


async def test_session_finalize_triggers_sync_from_session_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test an explicit finalized marker syncs from the recorded session start.

    Our 2026-04-05 real-session probe showed that finalized summary data only
    became visible once Ohme exposed a true completion edge. When the API does
    provide both ``session_start`` and ``session_finish``, we can safely anchor
    the resync to that completed session.
    """
    session_start = datetime(2026, 4, 6, 10, 15, tzinfo=dt_util.UTC)
    session_finish = datetime(2026, 4, 6, 12, 5, tzinfo=dt_util.UTC)

    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    mock_client.async_get_charge_session = _make_charge_session_side_effect(
        mock_client,
        [
            {
                "status": ChargerStatus.CHARGING,
                "session_start": session_start,
                "session_finish": None,
            },
            {
                "status": ChargerStatus.FINISHED,
                "session_start": session_start,
                "session_finish": session_finish,
            },
        ],
    )

    with patch(
        "homeassistant.components.ohme.coordinator.async_sync_session_energy_history",
        new=AsyncMock(return_value={"action": "window_sync"}),
    ) as mock_sync_session:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_sync_session.assert_awaited_once_with(
        hass,
        mock_config_entry,
        session_start=session_start,
        reason="session_finalized",
    )


async def test_finished_session_does_not_resync_after_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test seeded finished-session state does not retrigger a finalize sync.

    Startup recovery already reimports from the last imported hour overlap, so
    a restart into an already-finalized session should not look like a fresh
    completion event and cause a second bounded session sync.
    """
    session_start = datetime(2026, 4, 6, 10, 15, tzinfo=dt_util.UTC)
    session_finish = datetime(2026, 4, 6, 12, 5, tzinfo=dt_util.UTC)
    mock_client.status = ChargerStatus.FINISHED
    mock_client.session_start = session_start
    mock_client.session_finish = session_finish
    mock_client.async_get_charge_session = _make_charge_session_side_effect(
        mock_client,
        [
            {
                "status": ChargerStatus.FINISHED,
                "session_start": session_start,
                "session_finish": session_finish,
            }
        ],
    )

    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.ohme.coordinator.async_sync_session_energy_history",
            new=AsyncMock(return_value={"action": "window_sync"}),
        ) as mock_sync_session,
        patch(
            "homeassistant.components.ohme.coordinator.async_sync_repair_energy_history",
            new=AsyncMock(return_value={"action": "window_sync"}),
        ) as mock_sync_repair,
    ):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_sync_session.assert_not_awaited()
    mock_sync_repair.assert_not_awaited()


async def test_finished_without_marker_waits_for_disconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test plain finished state waits for disconnect before syncing.

    The 2026-04-05 probe entered ``FINISHED_CHARGE`` at 07:54 local time, but
    ``charge_stats_energy_wh`` and the fixed-range summary total both stayed
    stale until the charger became ``DISCONNECTED`` at 09:21. Only that
    disconnect edge exposed ``finish_time_local`` and the finalized summary
    totals, so a bare finished state without a finish marker must not trigger
    an early sync.
    """
    session_start = datetime(2026, 4, 6, 10, 15, tzinfo=dt_util.UTC)
    session_finish = datetime(2026, 4, 6, 14, 21, tzinfo=dt_util.UTC)

    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    mock_client.async_get_charge_session = _make_charge_session_side_effect(
        mock_client,
        [
            {
                "status": ChargerStatus.CHARGING,
                "session_start": session_start,
                "session_finish": None,
            },
            {
                "status": ChargerStatus.FINISHED,
                "session_start": session_start,
                "session_finish": None,
            },
            {
                "status": ChargerStatus.UNPLUGGED,
                "session_start": session_start,
                "session_finish": session_finish,
            },
        ],
    )

    with (
        patch(
            "homeassistant.components.ohme.coordinator.async_sync_session_energy_history",
            new=AsyncMock(return_value={"action": "window_sync"}),
        ) as mock_sync_session,
        patch(
            "homeassistant.components.ohme.coordinator.async_sync_repair_energy_history",
            new=AsyncMock(return_value={"action": "window_sync"}),
        ) as mock_sync_repair,
    ):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_sync_repair.assert_not_awaited()
    mock_sync_session.assert_awaited_once_with(
        hass,
        mock_config_entry,
        session_start=session_start,
        reason="session_finalized",
    )


async def test_missing_session_marker_falls_back_to_repair_sync(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test unplug without session markers falls back to bounded repair sync.

    The same probe showed unplug as the point where finalized summary data
    becomes visible. If Ohme gives us that disconnect edge but no usable
    ``session_start`` / ``session_finish`` anchors, we still repair the recent
    bounded window rather than guessing a full-session anchor.
    """
    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    mock_client.async_get_charge_session = _make_charge_session_side_effect(
        mock_client,
        [
            {
                "status": ChargerStatus.CHARGING,
                "session_start": None,
                "session_finish": None,
            },
            {
                "status": ChargerStatus.UNPLUGGED,
                "session_start": None,
                "session_finish": None,
            },
        ],
    )

    with patch(
        "homeassistant.components.ohme.coordinator.async_sync_repair_energy_history",
        new=AsyncMock(return_value={"action": "window_sync"}),
    ) as mock_sync_repair:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_sync_repair.assert_awaited_once_with(
        hass,
        mock_config_entry,
        reason="session_marker_missing",
    )


async def test_finalize_schedules_one_delayed_retry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test a finalized session schedules exactly one delayed retry.

    Ohme summary data is convergent rather than live. We resync immediately
    when a completion edge appears, then schedule one delayed retry so a late
    finalized summary bucket can still be picked up without polling summary
    endpoints continuously.
    """
    session_start = datetime(2026, 4, 6, 10, 15, tzinfo=dt_util.UTC)
    session_finish = datetime(2026, 4, 6, 12, 5, tzinfo=dt_util.UTC)

    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    mock_client.async_get_charge_session = _make_charge_session_side_effect(
        mock_client,
        [
            {
                "status": ChargerStatus.CHARGING,
                "session_start": session_start,
                "session_finish": None,
            },
            {
                "status": ChargerStatus.FINISHED,
                "session_start": session_start,
                "session_finish": session_finish,
            },
            {
                "status": ChargerStatus.FINISHED,
                "session_start": session_start,
                "session_finish": session_finish,
            },
        ],
    )

    with patch(
        "homeassistant.components.ohme.coordinator.async_sync_session_energy_history",
        new=AsyncMock(return_value={"action": "window_sync"}),
    ) as mock_sync_session:
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        freezer.tick(timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_sync_session.await_count == 2
    first_call, second_call = mock_sync_session.await_args_list
    assert first_call.kwargs["reason"] == "session_finalized"
    assert second_call.kwargs["reason"] == "session_finalized_retry"


async def test_daily_repair_runs_over_bounded_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the daily repair timer uses the bounded repair helper."""
    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.ohme.coordinator.async_sync_repair_energy_history",
        new=AsyncMock(return_value={"action": "window_sync"}),
    ) as mock_sync_repair:
        freezer.tick(timedelta(days=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_sync_repair.assert_awaited_once_with(
        hass,
        mock_config_entry,
        reason="daily_repair",
    )


async def test_regular_charge_session_poll_no_longer_queries_summary(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test steady-state polling no longer hits the summary endpoint."""
    with patch(
        "homeassistant.components.ohme.async_ensure_energy_history",
        new=AsyncMock(return_value={"action": "noop"}),
    ):
        await setup_integration(hass, mock_config_entry)

    await_count_before = mock_client.async_get_charge_summary.await_count

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_client.async_get_charge_summary.await_count == await_count_before == 0


async def test_repair_window_uses_recent_sync_days(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the bounded repair window is derived from DEFAULT_RECENT_SYNC_DAYS."""
    window_end = datetime(2026, 4, 6, 12, 0, tzinfo=dt_util.UTC)
    assert repair_window_start(mock_config_entry, window_end) == datetime(
        2026,
        3,
        30,
        13,
        0,
        tzinfo=dt_util.UTC,
    )
