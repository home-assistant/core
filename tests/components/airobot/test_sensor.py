"""Tests for the Airobot sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.freeze_time("2024-01-01 00:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_availability_without_optional_sensors(
    hass: HomeAssistant,
) -> None:
    """Test sensors are not created when optional hardware is not present."""
    # Default mock has no floor sensor, CO2, or AQI - they should not be created
    assert hass.states.get("sensor.test_thermostat_floor_temperature") is None
    assert hass.states.get("sensor.test_thermostat_carbon_dioxide") is None
    assert hass.states.get("sensor.test_thermostat_air_quality_index") is None
