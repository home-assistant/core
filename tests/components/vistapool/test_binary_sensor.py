"""Tests for the Vistapool binary_sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test all binary sensor entities for the default fixture."""
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vistapool.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensors_hydrolysis_branch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the hydrolysis (non-electrolysis) branch creates the right entity."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasHidro": 1, "version": 1},
        "hidro": {"is_electrolysis": False, "low": 1},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_hydrolysis_low").state == STATE_ON
    assert hass.states.get("binary_sensor.my_pool_electrolysis_low") is None


async def test_binary_sensors_all_modules_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test every module-gated binary sensor comes up when all `has*` flags are set."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {
            "hasCD": 1,
            "hasCL": 1,
            "hasIO": 1,
            "hasPH": 1,
            "hasRX": 1,
            "hasHidro": 1,
            "version": 1,
        },
        "modules": {
            "ph": {"tank": 0, "pump_high_on": 0, "pump_low_on": 0, "al3": 0},
            "rx": {"tank": 0, "pump_status": 0},
            "cl": {"tank": 0, "pump_status": 0},
            "cd": {"tank": 0},
        },
        "hidro": {"is_electrolysis": True, "fl1": 0, "fl2": 0, "cover": 0, "low": 0},
        "filtration": {"status": 0},
        "backwash": {"status": 0},
        "relays": {"filtration": {"heating": {"status": 0}}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        "binary_sensor.my_pool_hidro_fl2",
        "binary_sensor.my_pool_chlorine_pump",
        "binary_sensor.my_pool_redox_pump",
        "binary_sensor.my_pool_ph_pump_alarm",
        "binary_sensor.my_pool_dosing_tank",
    ):
        assert hass.states.get(entity_id) is not None


async def test_binary_sensors_dosing_tank_low(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the dosing-tank sensor reports `on` when any installed tank is low."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasPH": 1, "version": 1},
        "modules": {"ph": {"tank": 1}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_dosing_tank").state == STATE_ON


async def test_binary_sensors_dosing_tank_unknown_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the dosing-tank sensor reports unknown when no tank values are available."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasPH": 1, "version": 1},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_dosing_tank").state == STATE_UNKNOWN


async def test_binary_sensors_fl2_requires_hidro(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test hidro_fl2 is not created when hasCL is set but hasHidro is not."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasCL": 1, "hasHidro": 0, "version": 1},
        "modules": {"cl": {"pump_status": 0, "tank": 0}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_hidro_fl2") is None
    assert hass.states.get("binary_sensor.my_pool_chlorine_pump") is not None


async def test_binary_sensors_multi_pool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test setup creates binary sensors for every pool on the account."""
    mock_vistapool_client.get_pools.return_value = {
        "pool_a": "Pool A",
        "pool_b": "Pool B",
    }
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.pool_a_filtration").state == STATE_ON
    assert hass.states.get("binary_sensor.pool_b_filtration").state == STATE_ON
