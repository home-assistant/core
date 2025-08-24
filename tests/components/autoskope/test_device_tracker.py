"""Test Autoskope device tracker."""

from unittest.mock import patch

from autoskope_client.models import Vehicle, VehiclePosition

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test device tracker setup."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = mock_vehicles_list

        # Setup entry
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check device tracker entity was created
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        assert len(entries) == 1
        entity = entries[0]
        assert entity.domain == DEVICE_TRACKER_DOMAIN
        assert entity.unique_id == f"autoskope_{mock_vehicles_list[0].id}"


async def test_device_tracker_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test device tracker attributes."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = mock_vehicles_list

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        vehicle = mock_vehicles_list[0]
        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check vehicle-specific attributes
        assert state.attributes["battery_voltage"] == vehicle.battery_voltage
        assert state.attributes["external_voltage"] == vehicle.external_voltage
        assert state.attributes["gps_quality"] == vehicle.gps_quality
        assert state.attributes["imei"] == vehicle.imei
        assert "activity" in state.attributes
        assert "gps_accuracy" in state.attributes

        # Check coordinates
        if vehicle.position:
            assert state.attributes["latitude"] == vehicle.position.latitude
            assert state.attributes["longitude"] == vehicle.position.longitude
            assert state.attributes["speed"] == vehicle.position.speed


async def test_device_tracker_moving_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device tracker with moving vehicle."""
    # Create moving vehicle data
    moving_position = VehiclePosition(
        latitude=50.1109221,
        longitude=8.6821267,
        speed=50,  # Moving fast
        timestamp="2025-05-28T10:00:00Z",
        park_mode=False,
    )

    moving_vehicle = Vehicle(
        id="12345",
        name="Test Vehicle",
        position=moving_position,
        external_voltage=12.5,
        battery_voltage=3.7,
        gps_quality=1.2,
        imei="123456789012345",
        model="Autoskope",
    )

    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = [moving_vehicle]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check moving vehicle attributes
        assert state.attributes["speed"] == 50
        assert state.attributes["activity"] == "moving"


async def test_device_tracker_parked_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device tracker with parked vehicle."""
    # Create parked vehicle data
    parked_position = VehiclePosition(
        latitude=50.1109221,
        longitude=8.6821267,
        speed=0,
        timestamp="2025-05-28T10:00:00Z",
        park_mode=True,  # Explicitly parked
    )

    parked_vehicle = Vehicle(
        id="12345",
        name="Test Vehicle",
        position=parked_position,
        external_voltage=12.5,
        battery_voltage=3.7,
        gps_quality=1.2,
        imei="123456789012345",
        model="Autoskope",
    )

    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = [parked_vehicle]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check parked vehicle attributes
        assert state.attributes["speed"] == 0
        assert state.attributes["park_mode"] is True
        assert state.attributes["activity"] == "parked"


async def test_device_tracker_no_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device tracker with vehicle that has no position data."""
    vehicle_no_position = Vehicle(
        id="12345",
        name="Test Vehicle",
        position=None,  # No position data
        external_voltage=12.5,
        battery_voltage=3.7,
        gps_quality=1.2,
        imei="123456789012345",
        model="Autoskope",
    )

    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = [vehicle_no_position]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check that position attributes are None or not present
        assert state.attributes.get("latitude") is None
        assert state.attributes.get("longitude") is None
        assert state.attributes["activity"] == "unknown"


async def test_device_tracker_gps_accuracy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test GPS accuracy calculation."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = mock_vehicles_list

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # GPS accuracy should be calculated from HDOP
        gps_accuracy = state.attributes.get("gps_accuracy")
        assert gps_accuracy is not None
        assert isinstance(gps_accuracy, int)
        assert gps_accuracy >= 5  # Minimum accuracy


async def test_device_tracker_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test device tracker device info."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = mock_vehicles_list

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Get device registry entry
        device_registry = dr.async_get(hass)
        devices = device_registry.devices

        vehicle = mock_vehicles_list[0]
        vehicle_device = None
        for device in devices.values():
            if vehicle.id in str(device.identifiers):
                vehicle_device = device
                break

        assert vehicle_device is not None
        assert vehicle_device.name == vehicle.name
        assert "Autoskope" in str(vehicle_device.manufacturer)


async def test_device_tracker_entity_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test device tracker entity availability logic."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        # Initially have vehicle
        mock_get_vehicles.return_value = mock_vehicles_list

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entity exists and is available
        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None
        assert state.state != "unavailable"

        # Update to empty vehicles list
        mock_get_vehicles.return_value = []

        # Trigger coordinator update
        coordinator = mock_config_entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Check entity availability behavior
        state = hass.states.get("device_tracker.test_vehicle")
        # Entity should still exist but may be unavailable
        assert state is not None
