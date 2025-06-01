"""Test Adax sensor entity."""

from unittest.mock import AsyncMock

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


async def test_sensor_cloud(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor setup for cloud connection."""
    await setup_integration(hass, mock_cloud_config_entry)
    # Now we use fetch_rooms_info as primary method
    mock_adax_cloud.fetch_rooms_info.assert_called_once()

    # Test individual energy sensor
    entity_id = "sensor.room_1_energy_1"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1.5"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "1_1_energy"


async def test_sensor_local_not_created(
    hass: HomeAssistant,
    mock_adax_local: AsyncMock,
    mock_local_config_entry,
) -> None:
    """Test that sensors are not created for local connection."""
    await setup_integration(hass, mock_local_config_entry)

    # No sensor entities should be created for local connection
    sensor_entities = hass.states.async_entity_ids(SENSOR_DOMAIN)
    adax_sensors = [e for e in sensor_entities if "adax" in e or "room" in e]
    assert len(adax_sensors) == 0


async def test_multiple_devices_create_individual_sensors(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry,
) -> None:
    """Test that multiple devices create individual sensors."""
    # Mock multiple devices for both fetch_rooms_info and get_rooms (fallback)
    multiple_devices_data = [
        {
            "id": "1",
            "homeId": "1",
            "name": "Room 1",
            "temperature": 15,
            "targetTemperature": 20,
            "heatingEnabled": True,
            "energyWh": 1500,
        },
        {
            "id": "2",
            "homeId": "1",
            "name": "Room 2",
            "temperature": 18,
            "targetTemperature": 22,
            "heatingEnabled": True,
            "energyWh": 2500,
        },
    ]

    mock_adax_cloud.fetch_rooms_info.return_value = multiple_devices_data
    mock_adax_cloud.get_rooms.return_value = multiple_devices_data

    await setup_integration(hass, mock_cloud_config_entry)

    # Test that individual sensors are created for each device
    entity_id_1 = "sensor.room_1_energy_1"
    state_1 = hass.states.get(entity_id_1)
    assert state_1
    assert state_1.state == "1.5"  # 1500 Wh = 1.5 kWh

    entity_id_2 = "sensor.room_2_energy_2"
    state_2 = hass.states.get(entity_id_2)
    assert state_2
    assert state_2.state == "2.5"  # 2500 Wh = 2.5 kWh


async def test_fallback_to_get_rooms(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry,
) -> None:
    """Test fallback to get_rooms when fetch_rooms_info returns empty list."""
    # Mock fetch_rooms_info to return empty list, get_rooms to return data
    mock_adax_cloud.fetch_rooms_info.return_value = []
    mock_adax_cloud.get_rooms.return_value = [
        {
            "id": "1",
            "homeId": "1",
            "name": "Room 1",
            "temperature": 15,
            "targetTemperature": 20,
            "heatingEnabled": True,
            "energyWh": 0,  # No energy data from get_rooms
        }
    ]

    await setup_integration(hass, mock_cloud_config_entry)

    # Should call both methods
    mock_adax_cloud.fetch_rooms_info.assert_called_once()
    mock_adax_cloud.get_rooms.assert_called_once()

    # Test that sensor is still created with fallback data
    entity_id = "sensor.room_1_energy_1"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.0"  # No energy data from fallback
