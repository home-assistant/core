"""Test Hydrawise sensor."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Controller, ControllerWaterUseSummary, User, Zone
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hydrawise.const import (
    MAIN_SCAN_INTERVAL,
    WATER_USE_SCAN_INTERVAL,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_all_sensors(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all sensors are working."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [Platform.SENSOR],
    ):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_suspended_state(
    hass: HomeAssistant,
    zones: list[Zone],
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    """Test sensor states."""
    zones[0].scheduled_runs.next_run = None
    await mock_add_config_entry()

    next_cycle = hass.states.get("sensor.zone_one_next_cycle")
    assert next_cycle is not None
    assert next_cycle.state == "unknown"


@pytest.mark.freeze_time("2024-11-01 00:00:00+00:00")
async def test_usage_refresh(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    controller_water_use_summary: ControllerWaterUseSummary,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that water usage summaries refresh less frequently than other data."""
    assert hass.states.get("sensor.zone_one_daily_active_water_use") is not None
    mock_pydrawise.get_water_use_summary.assert_called_once()

    # Make the coordinator refresh data.
    mock_pydrawise.get_water_use_summary.reset_mock()
    freezer.tick(MAIN_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # Make sure we didn't fetch water use summary again.
    mock_pydrawise.get_water_use_summary.assert_not_called()

    # Wait for enough time to pass for a water use summary fetch.
    mock_pydrawise.get_water_use_summary.return_value = controller_water_use_summary
    freezer.tick(WATER_USE_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_pydrawise.get_water_use_summary.assert_called_once()


async def test_usage_end_of_day_and_midnight_reset(
    hass: HomeAssistant,
    controller: Controller,
    controller_water_use_summary: ControllerWaterUseSummary,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test pre-midnight capture, post-midnight reset, and hourly re-spreading."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    local_tz = ZoneInfo("America/Los_Angeles")
    await hass.config.async_set_time_zone("America/Los_Angeles")
    freezer.move_to(datetime(2024, 11, 1, 23, 6, 0, tzinfo=local_tz))

    with patch(
        "homeassistant.components.hydrawise.coordinator.randrange",
        # pre-midnight offset: 60s (23:59:00), post-midnight offset: 45s
        # (00:00:45), post-midnight re-spread interval: 37 min.
        side_effect=[60, 45, 37 * 60],
    ):
        await mock_add_config_entry()
        mock_pydrawise.get_water_use_summary.assert_called_once()
        mock_pydrawise.get_water_use_summary.reset_mock()

        # Simulate a late-evening run completing before midnight.
        controller_water_use_summary.total_use = 500.0
        controller_water_use_summary.total_active_use = 480.0
        controller_water_use_summary.total_inactive_use = 20.0
        controller_water_use_summary.active_use_by_zone_id[5965395] = 150.0

        # Pre-midnight poll runs at 23:59:00 (53m later, before the 60m interval).
        freezer.tick(timedelta(minutes=53, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_pydrawise.get_water_use_summary.assert_called_once_with(
            controller,
            datetime(2024, 11, 1, 0, 0, 0, tzinfo=local_tz),
            datetime(2024, 11, 1, 23, 59, 1, tzinfo=local_tz),
        )
        total_use = hass.states.get("sensor.home_controller_daily_total_water_use")
        assert total_use is not None
        assert total_use.state == "500.0"
        zone_two_use = hass.states.get("sensor.zone_two_daily_active_water_use")
        assert zone_two_use is not None
        assert zone_two_use.state == "150.0"
        inactive_use = hass.states.get(
            "sensor.home_controller_daily_inactive_water_use"
        )
        assert inactive_use is not None
        assert inactive_use.state == "20.0"

        # Simulate the new day starting with zero usage.
        mock_pydrawise.get_water_use_summary.reset_mock()
        controller_water_use_summary.total_use = 0.0
        controller_water_use_summary.total_active_use = 0.0
        controller_water_use_summary.total_inactive_use = 0.0
        controller_water_use_summary.active_use_by_zone_id[5965395] = 0.0

        # Post-midnight reset poll fires at 00:00:45 (1m45s after 23:59:01).
        freezer.tick(timedelta(minutes=1, seconds=46))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_pydrawise.get_water_use_summary.assert_called_once_with(
            controller,
            datetime(2024, 11, 2, 0, 0, 0, tzinfo=local_tz),
            datetime(2024, 11, 2, 0, 0, 47, tzinfo=local_tz),
        )
        total_use = hass.states.get("sensor.home_controller_daily_total_water_use")
        assert total_use is not None
        assert total_use.state == "0.0"

        # Next poll is re-spread to 37 minutes later (not phase-locked to :59).
        mock_pydrawise.get_water_use_summary.reset_mock()
        freezer.tick(timedelta(minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_pydrawise.get_water_use_summary.assert_not_called()

        freezer.tick(timedelta(minutes=7, seconds=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_pydrawise.get_water_use_summary.assert_called_once()

        # Subsequent polls return to the normal 60-minute interval.
        mock_pydrawise.get_water_use_summary.reset_mock()
        freezer.tick(timedelta(minutes=50))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_pydrawise.get_water_use_summary.assert_not_called()

        freezer.tick(timedelta(minutes=10, seconds=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_pydrawise.get_water_use_summary.assert_called_once()


async def test_usage_end_of_day_no_duplicate_when_close_to_target(
    hass: HomeAssistant,
    controller: Controller,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll already within 30s of the pre-midnight target jumps to reset."""
    local_tz = ZoneInfo("America/Los_Angeles")
    await hass.config.async_set_time_zone("America/Los_Angeles")
    freezer.move_to(datetime(2024, 11, 1, 23, 58, 45, tzinfo=local_tz))

    with patch(
        "homeassistant.components.hydrawise.coordinator.randrange",
        side_effect=[60, 45, 30 * 60],
    ):
        await mock_add_config_entry()
        mock_pydrawise.get_water_use_summary.reset_mock()

        # Passing 23:59:00 should not trigger a duplicate poll 15s later.
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_pydrawise.get_water_use_summary.assert_not_called()

        # Instead the next poll fires at the post-midnight reset (00:00:45).
        freezer.tick(timedelta(minutes=1, seconds=32))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        mock_pydrawise.get_water_use_summary.assert_called_once_with(
            controller,
            datetime(2024, 11, 2, 0, 0, 0, tzinfo=local_tz),
            datetime(2024, 11, 2, 0, 0, 47, tzinfo=local_tz),
        )


async def _disable_polling(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    hass.config_entries.async_update_entry(config_entry, pref_disable_polling=True)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()


async def _unload_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(_disable_polling, id="polling_disabled"),
        pytest.param(_unload_entry, id="entry_unloaded"),
    ],
)
async def test_usage_end_of_day_refresh_skipped(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
    action: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """Test pre-midnight refresh is skipped when polling is disabled or unloaded."""
    local_tz = ZoneInfo("America/Los_Angeles")
    await hass.config.async_set_time_zone("America/Los_Angeles")
    freezer.move_to(datetime(2024, 11, 1, 23, 6, 0, tzinfo=local_tz))

    with patch(
        "homeassistant.components.hydrawise.coordinator.randrange",
        return_value=60,
    ):
        config_entry = await mock_add_config_entry()
        await action(hass, config_entry)
        mock_pydrawise.get_water_use_summary.reset_mock()

        freezer.tick(timedelta(minutes=54))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_pydrawise.get_water_use_summary.assert_not_called()


async def test_no_sensor_and_water_state(
    hass: HomeAssistant,
    controller: Controller,
    controller_water_use_summary: ControllerWaterUseSummary,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    """Test sensors in the absence of flow and rain sensors."""
    controller.sensors = []
    controller_water_use_summary.total_use = None
    controller_water_use_summary.total_active_use = None
    controller_water_use_summary.total_inactive_use = None
    controller_water_use_summary.active_use_by_zone_id = {}
    await mock_add_config_entry()

    assert hass.states.get("sensor.zone_one_daily_active_water_use") is None
    assert hass.states.get("sensor.zone_two_daily_active_water_use") is None
    assert hass.states.get("sensor.home_controller_daily_active_water_use") is None
    assert hass.states.get("sensor.home_controller_daily_inactive_water_use") is None
    assert hass.states.get("binary_sensor.home_controller_rain_sensor") is None

    sensor = hass.states.get("sensor.home_controller_daily_active_watering_time")
    assert sensor is not None
    assert sensor.state == "123.0"

    sensor = hass.states.get("sensor.zone_one_daily_active_watering_time")
    assert sensor is not None
    assert sensor.state == "123.0"

    sensor = hass.states.get("sensor.zone_two_daily_active_watering_time")
    assert sensor is not None
    assert sensor.state == "0.0"

    sensor = hass.states.get("binary_sensor.home_controller_connectivity")
    assert sensor is not None
    assert sensor.state == "on"


@pytest.mark.parametrize(
    ("hydrawise_unit_system", "unit_system", "expected_state"),
    [
        ("imperial", METRIC_SYSTEM, "454.6279552584"),
        ("imperial", US_CUSTOMARY_SYSTEM, "120.1"),
        ("metric", METRIC_SYSTEM, "120.1"),
        ("metric", US_CUSTOMARY_SYSTEM, "31.7270634882136"),
    ],
)
async def test_volume_unit_conversion(
    hass: HomeAssistant,
    unit_system: UnitSystem,
    hydrawise_unit_system: str,
    expected_state: str,
    user: User,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    """Test volume unit conversion."""
    hass.config.units = unit_system
    user.units.units_name = hydrawise_unit_system
    await mock_add_config_entry()

    daily_active_water_use = hass.states.get("sensor.zone_one_daily_active_water_use")
    assert daily_active_water_use is not None
    assert daily_active_water_use.state == expected_state
