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

    # Test master energy sensor
    master_entity_id = "sensor.adax_total_energy"
    master_state = hass.states.get(master_entity_id)
    assert master_state
    assert master_state.state == "1.5"  # Same as individual since only one device
    assert master_state.attributes["unit_of_measurement"] == "kWh"
    assert master_state.attributes["device_class"] == "energy"
    assert master_state.attributes["state_class"] == "total_increasing"

    master_entry = entity_registry.async_get(master_entity_id)
    assert master_entry
    assert master_entry.unique_id == "1_adax_total_energy"


async def test_climate_energy_attributes(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry,
) -> None:
    """Test that climate entity has energy attributes."""
    await setup_integration(hass, mock_cloud_config_entry)

    entity_id = "climate.room_1"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["energy_kwh"] == 1.5
    assert state.attributes["energy_wh"] == 1500


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


async def test_master_sensor_sums_multiple_devices(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry,
) -> None:
    """Test that master sensor correctly sums multiple devices."""
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

    mock_adax_cloud.fetch_energy_info.return_value = [
        {"deviceId": "1", "energyWh": 1500},
        {"deviceId": "2", "energyWh": 2500},
    ]

    await setup_integration(hass, mock_cloud_config_entry)

    # Test that master sensor sums both devices
    master_entity_id = "sensor.adax_total_energy"
    master_state = hass.states.get(master_entity_id)
    assert master_state
    assert master_state.state == "4.0"  # 1.5 + 2.5 = 4.0 kWh


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
