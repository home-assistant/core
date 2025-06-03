"""Test Hydrawise sensor."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Controller, ControllerWaterUseSummary, User, Zone
import pytest
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

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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


async def test_no_sensor_and_water_state(
    hass: HomeAssistant,
    controller: Controller,
    controller_water_use_summary: ControllerWaterUseSummary,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    """Test rain sensor, flow sensor, and water use in the absence of flow and rain sensors."""
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
