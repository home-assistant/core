"""Tests for the Data Grand Lyon binary sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from data_grand_lyon_ha import VelovStationStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_VELOV_STATION

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_velov_binary_sensor_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test Vélo'v binary sensor entities with snapshot."""
    with patch(
        "homeassistant.components.data_grand_lyon.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        mock_velov_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_velov_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("station_status", "expected_state"),
    [
        pytest.param(VelovStationStatus.OPEN, "on", id="open"),
        pytest.param(VelovStationStatus.CLOSED, "off", id="closed"),
    ],
)
async def test_velov_binary_sensor_status(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    station_status: VelovStationStatus,
    expected_state: str,
) -> None:
    """Test Vélo'v binary sensor reflects station status."""
    mock_tcl_client.get_velov_stations.return_value = [
        replace(MOCK_VELOV_STATION, status=station_status)
    ]
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.velo_v_1001_station_open")
    assert state is not None
    assert state.state == expected_state


async def test_velov_binary_sensor_no_data(
    hass: HomeAssistant,
    mock_velov_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that Vélo'v binary sensor is unavailable when station not found."""
    mock_tcl_client.get_velov_stations.return_value = []
    mock_velov_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_velov_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.velo_v_1001_station_open")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
