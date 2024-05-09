"""Test Hydrawise sensor."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from pydrawise.schema import Controller, Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def test_no_sensor_and_water_state2(
    hass: HomeAssistant,
    controller: Controller,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    """Test rain sensor, flow sensor, and water use in the absence of flow and rain sensors."""
    controller.sensors = []
    await mock_add_config_entry()

    assert hass.states.get("sensor.zone_one_daily_active_water_use") is None
    assert hass.states.get("sensor.zone_two_daily_active_water_use") is None
    assert hass.states.get("sensor.home_controller_daily_active_water_use") is None
    assert hass.states.get("sensor.home_controller_daily_inactive_water_use") is None
    assert hass.states.get("binary_sensor.home_controller_rain_sensor") is None

    sensor = hass.states.get("binary_sensor.home_controller_connectivity")
    assert sensor is not None
    assert sensor.state == "on"
