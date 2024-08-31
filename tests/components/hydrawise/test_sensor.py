"""Test Hydrawise sensor."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from pydrawise.schema import Controller, ControllerWaterUseSummary, User, Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from tests.common import MockConfigEntry, snapshot_platform


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
