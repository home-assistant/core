"""Test the Sunsynk sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from sunsynk.exceptions import SunsynkConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunsynk.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID_GRID_POWER = "sensor.garage_inverter_grid_power"


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

    mock_sunsynk_client.get_inverter_realtime_grid.side_effect = SunsynkConnectionError
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == STATE_UNAVAILABLE

    mock_sunsynk_client.get_inverter_realtime_grid.side_effect = None
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"


async def test_sensors_unavailable_when_inverter_is_removed(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors become unavailable when the inverter is no longer listed."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"

    mock_sunsynk_client.get_inverters.return_value = []
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_power_sensors_use_total_of_all_phases(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the grid and load power sensors report the total across all phases."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_GRID_POWER).state == "610.0"
    assert hass.states.get("sensor.garage_inverter_load_power").state == "3427.0"


@pytest.mark.usefixtures("mock_sunsynk_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a device is created for each inverter."""
    await setup_integration(hass, mock_config_entry)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 2
    assert devices == snapshot
