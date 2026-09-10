"""Test the Sunsynk sensors."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from sunsynk.exceptions import SunsynkConnectionError
from sunsynk.grid import Grid
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunsynk.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID_GRID_POWER = "sensor.garage_inverter_grid_power"
ENTITY_ID_GRID_POWER_2 = "sensor.inverter_2938475610_grid_power"


@pytest.mark.usefixtures("mock_sunsynk_client", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_unavailable_on_error(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors become unavailable when an update fails."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"

    grid = mock_sunsynk_client.get_inverter_realtime_grid.side_effect
    mock_sunsynk_client.get_inverter_realtime_grid.side_effect = SunsynkConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == STATE_UNAVAILABLE

    mock_sunsynk_client.get_inverter_realtime_grid.side_effect = grid
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"


async def test_one_inverter_unavailable(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing inverter does not affect the other inverters."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"
    assert hass.states.get(ENTITY_ID_GRID_POWER_2).state == "610.0"

    grid = mock_sunsynk_client.get_inverter_realtime_grid.side_effect

    def failing_grid(sn: str) -> Grid:
        if sn == "2938475610":
            raise SunsynkConnectionError
        return grid(sn)

    mock_sunsynk_client.get_inverter_realtime_grid.side_effect = failing_grid
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"
    assert hass.states.get(ENTITY_ID_GRID_POWER_2).state == STATE_UNAVAILABLE

    mock_sunsynk_client.get_inverter_realtime_grid.side_effect = grid
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER_2).state == "610.0"


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_power_sensors_use_total_of_all_phases(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the grid and load power sensors report the total across all phases."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"
    assert hass.states.get("sensor.garage_inverter_load_power").state == "3427.0"


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_no_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an inverter without a battery gets no battery device or entities."""
    await setup_integration(hass, mock_config_entry)
    entry_id = mock_config_entry.entry_id
    inverter = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1029384756"), entry_id
    )
    battery = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1029384756_battery"), entry_id
    )
    assert inverter is not None
    assert battery is not None
    assert battery.via_device_id == inverter.id
    assert hass.states.get("sensor.battery_1029384756_state_of_charge").state == "20.0"

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "2938475610_battery"), entry_id
        )
        is None
    )
    assert hass.states.get("sensor.battery_2938475610_state_of_charge") is None
