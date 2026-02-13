"""Test the Rotarex sensors."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.rotarex.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_rotarex_api")


async def test_sensors_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensors are created for each tank."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # Verify sensors for tank1
    level_entity = entity_registry.async_get("sensor.tank_1_level")
    assert level_entity
    assert level_entity.unique_id == "tank1-guid_level"

    battery_entity = entity_registry.async_get("sensor.tank_1_battery")
    assert battery_entity
    assert battery_entity.unique_id == "tank1-guid_battery"

    last_sync_entity = entity_registry.async_get("sensor.tank_1_last_synchronization")
    assert last_sync_entity
    assert last_sync_entity.unique_id == "tank1-guid_last_sync"

    # Verify sensors for tank2
    level_entity_2 = entity_registry.async_get("sensor.tank_2_level")
    assert level_entity_2
    assert level_entity_2.unique_id == "tank2-guid_level"


async def test_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensor states are correct."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check level sensor (should use latest sync data)
    level_state = hass.states.get("sensor.tank_1_level")
    assert level_state
    assert level_state.state == "70.0"
    assert level_state.attributes["unit_of_measurement"] == PERCENTAGE

    # Check battery sensor
    battery_state = hass.states.get("sensor.tank_1_battery")
    assert battery_state
    assert battery_state.state == "80.0"
    assert battery_state.attributes["unit_of_measurement"] == PERCENTAGE

    # Check last sync sensor (timestamp)
    last_sync_state = hass.states.get("sensor.tank_1_last_synchronization")
    assert last_sync_state
    assert last_sync_state.state == "2024-01-02T12:00:00+00:00"


async def test_sensor_uses_latest_sync(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensors use the most recent synchronization data."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Tank 1 has two syncs: 2024-01-01 and 2024-01-02
    # Should use the latest (2024-01-02)
    level_state = hass.states.get("sensor.tank_1_level")
    assert level_state.state == "70.0"  # From 2024-01-02, not 75.5 from 2024-01-01


async def test_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensors have correct device info."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    level_entity = entity_registry.async_get("sensor.tank_1_level")

    assert level_entity
    assert level_entity.device_id

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(level_entity.device_id)
    assert device
    assert device.name == "Tank 1"
    assert device.manufacturer == "Rotarex"
    assert device.model == "DIMES SRG"
    assert (DOMAIN, "tank1-guid") in device.identifiers


async def test_sensor_no_extra_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test sensors don't have extra attributes (they're separate sensors now)."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Level sensor should not have extra attributes
    level_state = hass.states.get("sensor.tank_1_level")
    assert level_state
    assert "last_sync" not in level_state.attributes

    # Battery sensor should not have last_sync in attributes
    battery_state = hass.states.get("sensor.tank_1_battery")
    assert battery_state
    assert "last_sync" not in battery_state.attributes
