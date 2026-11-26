"""Tests for WATERCryst BIOCAT sensors."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .common import InitIntegrationFunc


@pytest.mark.usefixtures("setup_integration")
async def test_all_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the setup of all sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_mandatory_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    init_integration: InitIntegrationFunc,
) -> None:
    """Test the setup of mandatory sensor entities."""
    data = mock_api_client.get_device_info.return_value
    data.has_flow_rate_sensor = False
    data.has_leakage_protection_system = False
    data.has_lime_scale_protection = False
    data.has_pressure_sensor = False
    data.has_temperature_sensor = False
    data.has_wireless_sensor_option = False

    assert await init_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
