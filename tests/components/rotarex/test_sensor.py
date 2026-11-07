"""Test the Rotarex sensors."""

from datetime import datetime
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from rotarex_dimes_srg_api import (
    InvalidAuth,
    RotarexConnectionError,
    RotarexSyncData,
    RotarexTank,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rotarex.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_rotarex_api")


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the coordinator poll again."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensor entities match snapshots."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device is created for each tank."""
    await setup_integration(hass, mock_config_entry)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 2
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"{device_entry.name}-device")


async def test_tank_without_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test a tank without a name is named after its GUID."""
    mock_rotarex_api.fetch_tanks.return_value = [
        RotarexTank(
            guid="no-name-guid",
            name=None,
            synch_datas=[
                RotarexSyncData(
                    synch_date=datetime(2024, 3, 1, 8, 0), level=42.0, battery=77.0
                )
            ],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.tank_no_name_guid_level")
    assert state
    assert state.state == "42.0"


async def test_tank_without_sync_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensors of a tank that never synchronized are unavailable."""
    mock_rotarex_api.fetch_tanks.return_value = [
        RotarexTank(guid="new-tank-guid", name="New tank", synch_datas=[])
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.new_tank_level")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("exception", [InvalidAuth, RotarexConnectionError])
async def test_update_error_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: type[Exception],
) -> None:
    """Test sensors become unavailable on update errors and recover."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get("sensor.tank_1_level"))
    assert state.state == "70.0"

    mock_rotarex_api.fetch_tanks.side_effect = exception
    await _refresh(hass, freezer)

    assert (state := hass.states.get("sensor.tank_1_level"))
    assert state.state == STATE_UNAVAILABLE

    mock_rotarex_api.fetch_tanks.side_effect = None
    await _refresh(hass, freezer)

    assert (state := hass.states.get("sensor.tank_1_level"))
    assert state.state == "70.0"


async def test_tank_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when a tank is no longer reported."""
    await setup_integration(hass, mock_config_entry)

    mock_rotarex_api.fetch_tanks.return_value = (
        mock_rotarex_api.fetch_tanks.return_value[1:]
    )
    await _refresh(hass, freezer)

    assert (state := hass.states.get("sensor.tank_1_level"))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get("sensor.tank_2_level"))
    assert state.state == "50.0"
