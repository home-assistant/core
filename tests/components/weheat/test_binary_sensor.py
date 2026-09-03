"""Tests for the weheat sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.const import STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_create_binary_entities(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating entities."""
    mock_weheat_discover.return_value = [mock_heat_pump_info]

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_offline_heat_pump_keeps_reporting(
    hass: HomeAssistant,
    mock_weheat_heat_pump: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the cloud calling a heat pump offline does not hide its last values."""
    mock_weheat_heat_pump.is_online = False

    with patch("homeassistant.components.weheat.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("binary_sensor.test_model_indoor_unit_water_pump").state
        == STATE_OFF
    )
