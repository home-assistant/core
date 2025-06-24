"""Test Adax sensor entity."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_cloud(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor setup for cloud connection."""
    with patch("homeassistant.components.adax.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_cloud_config_entry)
        # Now we use fetch_rooms_info as primary method
        mock_adax_cloud.fetch_rooms_info.assert_called_once()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_cloud_config_entry.entry_id
        )


async def test_sensor_local_not_created(
    hass: HomeAssistant,
    mock_adax_local: AsyncMock,
    mock_local_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors are not created for local connection."""
    with patch("homeassistant.components.adax.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_local_config_entry)

        # No sensor entities should be created for local connection
        sensor_entities = hass.states.async_entity_ids("sensor")
        adax_sensors = [e for e in sensor_entities if "adax" in e or "room" in e]
        assert len(adax_sensors) == 0


async def test_multiple_devices_create_individual_sensors(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
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

    with patch("homeassistant.components.adax.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_cloud_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_cloud_config_entry.entry_id
        )


async def test_fallback_to_get_rooms(
    hass: HomeAssistant,
    mock_adax_cloud: AsyncMock,
    mock_cloud_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
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

    with patch("homeassistant.components.adax.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_cloud_config_entry)

        # Should call both methods
        mock_adax_cloud.fetch_rooms_info.assert_called_once()
        mock_adax_cloud.get_rooms.assert_called_once()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_cloud_config_entry.entry_id
        )
