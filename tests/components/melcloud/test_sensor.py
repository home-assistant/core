"""Test the MELCloud sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

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
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("sensor.ecodan_outside_temperature", "7.5"),
        ("sensor.ecodan_tank_temperature", "48.0"),
        ("sensor.ecodan_flow_temperature", "38.5"),
        ("sensor.ecodan_return_temperature", "33.2"),
        ("sensor.ecodan_boiler_flow_temperature", "40.1"),
        ("sensor.ecodan_boiler_return_temperature", "35.3"),
        ("sensor.ecodan_mixing_tank_temperature", "42.0"),
        ("sensor.ecodan_condensing_temperature", "55.0"),
        ("sensor.ecodan_heat_pump_frequency", "52"),
        ("sensor.ecodan_demand_percentage", "75"),
        ("sensor.ecodan_energy_produced", "3.5"),
        ("sensor.ecodan_daily_heating_energy_consumed", "12.5"),
        ("sensor.ecodan_daily_hot_water_energy_consumed", "5.2"),
    ],
)
async def test_atw_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test ATW sensor entity states."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_get_devices")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("sensor.ecodan_zone_1_room_temperature", "22.5"),
        ("sensor.ecodan_zone_1_flow_temperature", "36.0"),
        ("sensor.ecodan_zone_1_return_temperature", "31.0"),
    ],
)
async def test_atw_zone_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test ATW zone sensor entity states."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_get_devices")
async def test_sensor_none_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Test sensor with None value reports unknown."""
    mock_atw_device.outside_temperature = None

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get("sensor.ecodan_outside_temperature")
    assert state is not None
    assert state.state == "unknown"


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
