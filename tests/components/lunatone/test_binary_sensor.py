"""Tests for the binary sensors provided by the Lunatone integration."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from lunatone_rest_api_client.models import ScanLineState, ScanState
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lunatone.coordinator import (
    DEFAULT_INFO_UPDATE_INTERVAL,
    DEFAULT_SCAN_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Lunatone DALI scan status value update."""
    scan_states = iter(
        (
            (ScanState.ADDRESSING, ScanLineState.ADDRESSING),
            (ScanState.DONE, ScanLineState.DONE),
        )
    )

    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.coordinator_scan

    async def fake_update():
        scan_state, line_scan_state = next(scan_states)
        scan_data = deepcopy(mock_lunatone_scan.data)
        scan_data.status = scan_state
        scan_data.lines[0].scan_state = line_scan_state
        mock_lunatone_scan.data = scan_data

    mock_lunatone_scan.async_update.side_effect = fake_update

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    assert all(entity.state == STATE_OFF for entity in entities)
    assert coordinator.update_interval == timedelta(seconds=10)

    freezer.tick(DEFAULT_SCAN_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    assert entities[0].state == STATE_ON
    assert entities[1].state == STATE_ON
    assert entities[2].state == STATE_OFF
    assert coordinator.update_interval == timedelta(seconds=1)

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entities = hass.states.async_all(Platform.BINARY_SENSOR)
    assert all(entity.state == STATE_OFF for entity in entities)
    assert coordinator.update_interval == timedelta(seconds=10)


async def test_line_scan_status_removed_with_line(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test line scan status sensors are removed with their line."""
    mock_lunatone_scan.data.lines = []

    await setup_integration(hass, mock_config_entry)

    entity_ids = (
        ("binary_sensor.dali_line_0_scan_status", STATE_OFF),
        ("binary_sensor.dali_line_1_scan_status", STATE_OFF),
    )
    for entity_id, expected_state in entity_ids:
        entity = hass.states.get(entity_id)
        assert entity and entity.state == expected_state

    new_info_data = deepcopy(mock_lunatone_info.data)
    new_info_data.lines = {}
    mock_lunatone_info.data = new_info_data

    freezer.tick(DEFAULT_INFO_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id, _ in entity_ids:
        assert hass.states.get(entity_id) is None
        assert entity_registry.async_get(entity_id) is None
