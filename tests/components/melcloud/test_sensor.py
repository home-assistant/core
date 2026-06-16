"""Test the MELCloud sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .conftest import MOCK_MAC, MOCK_SERIAL

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_get_devices")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensor entities with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_devices")
async def test_zone_sensor_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unique ID generation for zone sensors with multiple zones."""
    zone_2 = MagicMock()
    zone_2.zone_index = 2
    zone_2.name = "Zone 2"
    zone_2.room_temperature = 23.5
    zone_2.zone_flow_temperature = 37.0
    zone_2.zone_return_temperature = 32.0
    mock_atw_device.zones = [mock_atw_device.zones[0], zone_2]

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    # Zone 1 sensors - no zone suffix in unique ID
    entry = entity_registry.async_get("sensor.ecodan_zone_1_room_temperature")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}-{MOCK_MAC}-room_temperature"

    entry = entity_registry.async_get("sensor.ecodan_zone_1_flow_temperature")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}-{MOCK_MAC}-flow_temperature"

    entry = entity_registry.async_get("sensor.ecodan_zone_1_return_temperature")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}-{MOCK_MAC}-return_temperature"

    # Zone 2 sensors - with zone suffix in unique ID
    entry = entity_registry.async_get("sensor.ecodan_zone_2_room_temperature")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}-{MOCK_MAC}-room_temperature-zone-2"

    entry = entity_registry.async_get("sensor.ecodan_zone_2_flow_temperature")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}-{MOCK_MAC}-flow_temperature-zone-2"

    entry = entity_registry.async_get("sensor.ecodan_zone_2_return_temperature")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}-{MOCK_MAC}-return_temperature-zone-2"


@pytest.mark.usefixtures("mock_get_devices")
async def test_sensors_not_created_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Test sensors with enabled check are not created when property is None."""
    mock_atw_device.flow_temperature = None
    mock_atw_device.mixing_tank_temperature = None
    mock_atw_device.demand_percentage = None
    mock_atw_device.daily_heating_energy_consumed = None

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.ecodan_flow_temperature") is None
    assert hass.states.get("sensor.ecodan_mixing_tank_temperature") is None
    assert hass.states.get("sensor.ecodan_demand_percentage") is None
    assert hass.states.get("sensor.ecodan_daily_heating_energy_consumed") is None
