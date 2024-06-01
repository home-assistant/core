"""Test Hydrawise sensor."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Controller, Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hydrawise.const import SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def test_controller_offline(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    controller: Controller,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all binary sensors are working."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [Platform.SENSOR],
    ):
        config_entry = await mock_add_config_entry()
        controller.online = False
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_api_offline(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all binary sensors are working."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [Platform.SENSOR],
    ):
        config_entry = await mock_add_config_entry()
        mock_pydrawise.get_user.reset_mock(return_value=True)
        mock_pydrawise.get_user.side_effect = ClientError
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
