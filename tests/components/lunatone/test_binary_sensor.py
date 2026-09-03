"""Tests for the binary sensors provided by the Lunatone integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from lunatone_rest_api_client.models import ScanData, ScanState
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone binary sensor setup."""
    await setup_integration(hass, mock_config_entry)

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_sensor_value_update(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone DALI scan status value update."""
    scan_states = iter((ScanState.ADDRESSING, ScanState.DONE))

    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.coordinator_scan

    async def fake_update():
        scan_state = next(scan_states)
        mock_lunatone_scan.data = ScanData(status=scan_state)

    mock_lunatone_scan.async_update.side_effect = fake_update

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    assert entities[0].state == "off"
    assert coordinator.update_interval == timedelta(seconds=10)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    assert entities[0].state == "on"
    assert coordinator.update_interval == timedelta(seconds=1)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    assert entities[0].state == "off"
    assert coordinator.update_interval == timedelta(seconds=10)
