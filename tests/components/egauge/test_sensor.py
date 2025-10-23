"""Tests for the eGauge sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify device created with hostname
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123456")})
    assert device_entry
    assert device_entry.name == "egauge-home"
    assert device_entry.serial_number == "ABC123456"
    assert device_entry.manufacturer == "eGauge Systems"
    assert device_entry.model == "eGauge Energy Monitor"

    # Verify all entities assigned to device
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id

    # Verify only power sensors created (4 total: 2 power + 2 energy)
    # Temperature register should be gracefully ignored
    assert len(entity_entries) == 4


@pytest.mark.usefixtures("init_integration")
async def test_power_sensor_values(hass: HomeAssistant) -> None:
    """Test power sensor values are correct."""
    # Test Grid power sensor
    state = hass.states.get("sensor.egauge_home_grid")
    assert state
    assert state.state == "1500.0"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"
    assert state.attributes["state_class"] == "measurement"

    # Test Solar power sensor (negative indicates generation)
    state = hass.states.get("sensor.egauge_home_solar")
    assert state
    assert state.state == "-2500.0"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"


@pytest.mark.usefixtures("init_integration")
async def test_energy_sensor_values(hass: HomeAssistant) -> None:
    """Test energy sensor values and Ws to kWh conversion."""
    # Test Grid energy sensor - 450000000 Ws / 3600000 = 125 kWh
    state = hass.states.get("sensor.egauge_home_grid_energy")
    assert state
    assert state.state == "125.0"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"

    # Test Solar energy sensor - 315000000 Ws / 3600000 = 87.5 kWh
    state = hass.states.get("sensor.egauge_home_solar_energy")
    assert state
    assert state.state == "87.5"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy"
