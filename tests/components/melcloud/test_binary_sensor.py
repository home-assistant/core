"""Test the MELCloud binary sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
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
    """Test all binary sensor entities with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_devices")
@pytest.mark.parametrize(
    ("entity_id", "expected_state"),
    [
        ("binary_sensor.ecodan_boiler", STATE_ON),
        ("binary_sensor.ecodan_booster_heater_1", STATE_OFF),
        ("binary_sensor.ecodan_immersion_heater", STATE_OFF),
        ("binary_sensor.ecodan_water_pump_1", STATE_ON),
        ("binary_sensor.ecodan_water_pump_2", STATE_OFF),
        ("binary_sensor.ecodan_3_way_valve", STATE_ON),
    ],
)
async def test_atw_binary_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test ATW binary sensor entity states."""
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == expected_state


@pytest.mark.usefixtures("mock_get_devices")
async def test_binary_sensors_not_created_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Test binary sensors are not created when property is None."""
    # booster_heater2, booster_heater2plus, water_pump3, water_pump4, valve_2way
    # are already None in conftest and should not be created
    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    assert hass.states.get("binary_sensor.ecodan_booster_heater_2") is None
    assert hass.states.get("binary_sensor.ecodan_booster_heater_2_") is None
    assert hass.states.get("binary_sensor.ecodan_water_pump_3") is None
    assert hass.states.get("binary_sensor.ecodan_water_pump_4") is None
    assert hass.states.get("binary_sensor.ecodan_2_way_valve") is None


@pytest.mark.usefixtures("mock_get_devices")
async def test_binary_sensor_all_none_no_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_atw_device: MagicMock,
) -> None:
    """Test no binary sensors are created when all statuses are None."""
    mock_atw_device.boiler_status = None
    mock_atw_device.booster_heater1_status = None
    mock_atw_device.immersion_heater_status = None
    mock_atw_device.water_pump1_status = None
    mock_atw_device.water_pump2_status = None
    mock_atw_device.valve_3way_status = None

    await setup_platform(hass, mock_config_entry, [Platform.BINARY_SENSOR])

    entity_entries = er.async_entries_for_config_entry(
        er.async_get(hass), mock_config_entry.entry_id
    )
    assert len(entity_entries) == 0
