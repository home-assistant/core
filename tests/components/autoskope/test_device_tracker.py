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
    mock_autoskope_api,
) -> None:
    """Test device tracker setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list

        # Setup entry
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check device tracker entity was created
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        tracker_entries = [e for e in entries if e.domain == DEVICE_TRACKER_DOMAIN]
        assert len(tracker_entries) == 1
        entity = tracker_entries[0]
        assert entity.unique_id == f"{mock_vehicles_list[0].id}"


async def test_device_tracker_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
    mock_autoskope_api,
) -> None:
    """Test device tracker location attributes."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        vehicle = mock_vehicles_list[0]
        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check coordinates - these are still device_tracker attributes
        if vehicle.position:
            assert state.attributes["latitude"] == vehicle.position.latitude
            assert state.attributes["longitude"] == vehicle.position.longitude
            assert "gps_accuracy" in state.attributes

        # Check that extra attributes are NOT present (they are separate sensors now)
        assert "battery_voltage" not in state.attributes
        assert "external_voltage" not in state.attributes
        assert "speed" not in state.attributes
        assert "imei" not in state.attributes


async def test_device_tracker_moving_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
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

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = [moving_vehicle]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check icon for moving vehicle
        assert state.attributes["icon"] == "mdi:car-arrow-right"

        # Speed sensor is removed in minimal version
        # Just verify device tracker works
        assert state.attributes["latitude"] == 50.1109221
        assert state.attributes["longitude"] == 8.6821267


async def test_device_tracker_parked_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
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

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = [parked_vehicle]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check icon for parked vehicle
        assert state.attributes["icon"] == "mdi:car-brake-parking"

        # Sensors removed in minimal version
        # Just verify device tracker works with parked vehicle
        assert state.attributes["latitude"] == 50.1109221
        assert state.attributes["longitude"] == 8.6821267


async def test_device_tracker_no_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
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

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = [vehicle_no_position]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None

        # Check that position attributes are None or not present
        assert state.attributes.get("latitude") is None
        assert state.attributes.get("longitude") is None
        # Check icon when no position data
        assert state.attributes["icon"] == "mdi:car-clock"


async def test_device_tracker_gps_accuracy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
    mock_autoskope_api,
) -> None:
    """Test GPS accuracy calculation."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list

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
        coordinator = mock_config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Check entity availability behavior
        state = hass.states.get("device_tracker.test_vehicle")
        # Entity should still exist but may be unavailable
        assert state is not None
