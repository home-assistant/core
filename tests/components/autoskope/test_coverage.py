"""Tests for achieving 100% coverage of Autoskope integration."""

from unittest.mock import patch

from autoskope_client.models import Vehicle, VehiclePosition

from homeassistant.components.autoskope.coordinator import (
    AutoskopeDataUpdateCoordinator,
)
from homeassistant.components.autoskope.device_tracker import AutoskopeDeviceTracker
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_binary_sensor_no_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test binary sensor when coordinator has no data."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        # Start with vehicles
        mock_autoskope_api.get_vehicles.return_value = [
            Vehicle(
                id="12345",
                name="Test Vehicle",
                position=VehiclePosition(
                    latitude=50.1109221,
                    longitude=8.6821267,
                    speed=0,
                    timestamp="2025-05-28T10:00:00Z",
                    park_mode=False,
                ),
                external_voltage=12.5,
                battery_voltage=3.7,
                gps_quality=1.2,
                imei="123456789012345",
                model="Autoskope",
            )
        ]

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entity exists
        state = hass.states.get("binary_sensor.test_vehicle_motion")
        assert state is not None

        # Now simulate coordinator data being None
        coordinator = mock_config_entry.runtime_data
        coordinator.data = None

        # Force entity update
        coordinator.async_set_updated_data(None)
        await hass.async_block_till_done()

        # Entity should become unavailable when coordinator has no data
        state = hass.states.get("binary_sensor.test_vehicle_motion")
        assert state.state == "unavailable"

        # Test the edge case where coordinator has data but not for our vehicle
        coordinator.data = {
            "other_vehicle": Vehicle(
                id="99999",
                name="Other",
                position=None,
                external_voltage=12.5,
                battery_voltage=3.7,
                gps_quality=1.2,
                imei="999999999999999",
                model="Autoskope",
            )
        }
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        # Entity should still be unavailable as its vehicle is not in the data
        state = hass.states.get("binary_sensor.test_vehicle_motion")
        assert state.state == "unavailable"


async def test_sensor_no_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test sensor when coordinator has no data."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        # Start with vehicles
        mock_autoskope_api.get_vehicles.return_value = [
            Vehicle(
                id="12345",
                name="Test Vehicle",
                position=VehiclePosition(
                    latitude=50.1109221,
                    longitude=8.6821267,
                    speed=0,
                    timestamp="2025-05-28T10:00:00Z",
                    park_mode=False,
                ),
                external_voltage=12.5,
                battery_voltage=3.7,
                gps_quality=1.2,
                imei="123456789012345",
                model="Autoskope",
            )
        ]

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entity exists
        state = hass.states.get("sensor.test_vehicle_speed")
        assert state is not None

        # Now simulate coordinator data being None
        coordinator = mock_config_entry.runtime_data
        coordinator.data = None

        # Force entity update
        coordinator.async_set_updated_data(None)
        await hass.async_block_till_done()

        # Entity should become unavailable when coordinator has no data
        state = hass.states.get("sensor.test_vehicle_speed")
        assert state.state == "unavailable"

        # Test the edge case where coordinator has data but not for our vehicle
        coordinator.data = {
            "other_vehicle": Vehicle(
                id="99999",
                name="Other",
                position=None,
                external_voltage=12.5,
                battery_voltage=3.7,
                gps_quality=1.2,
                imei="999999999999999",
                model="Autoskope",
            )
        }
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        # Entity should still be unavailable as its vehicle is not in the data
        state = hass.states.get("sensor.test_vehicle_speed")
        assert state.state == "unavailable"


async def test_device_tracker_fallback_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test device tracker creates fallback device info when vehicle data is None."""
    # Test the fallback device info creation directly
    # Create a coordinator with no data
    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )
    coordinator.data = {}  # Empty data

    # Create tracker with vehicle_id that doesn't exist in coordinator data
    tracker = AutoskopeDeviceTracker(coordinator, "missing_vehicle")

    # Check that fallback device info was created
    assert tracker._attr_device_info is not None
    assert tracker._attr_device_info["name"] == "Autoskope Vehicle missing_vehicle"
    assert "manufacturer" in tracker._attr_device_info


async def test_device_tracker_no_gps_quality(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test device tracker location_accuracy when gps_quality is None or 0."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        # Vehicle with no gps_quality
        vehicle_no_gps = Vehicle(
            id="12345",
            name="Test Vehicle",
            position=VehiclePosition(
                latitude=50.1109221,
                longitude=8.6821267,
                speed=0,
                timestamp="2025-05-28T10:00:00Z",
                park_mode=False,
            ),
            external_voltage=12.5,
            battery_voltage=3.7,
            gps_quality=None,  # No GPS quality
            imei="123456789012345",
            model="Autoskope",
        )

        mock_autoskope_api.get_vehicles.return_value = [vehicle_no_gps]

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None
        # When gps_quality is None, location_accuracy should be 0
        assert state.attributes.get("gps_accuracy") == 0

        # Test with gps_quality = 0
        vehicle_zero_gps = Vehicle(
            id="12345",
            name="Test Vehicle",
            position=VehiclePosition(
                latitude=50.1109221,
                longitude=8.6821267,
                speed=0,
                timestamp="2025-05-28T10:00:00Z",
                park_mode=False,
            ),
            external_voltage=12.5,
            battery_voltage=3.7,
            gps_quality=0,  # Zero GPS quality
            imei="123456789012345",
            model="Autoskope",
        )

        mock_autoskope_api.get_vehicles.return_value = [vehicle_zero_gps]

        # Update coordinator
        coordinator = mock_config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None
        # When gps_quality is 0, location_accuracy should be 0
        assert state.attributes.get("gps_accuracy") == 0


async def test_device_tracker_longitude_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test device tracker longitude property returns None when no position."""
    # Test directly the longitude method to ensure coverage
    # Create coordinator with vehicle without position
    coordinator = AutoskopeDataUpdateCoordinator(
        hass, api=mock_autoskope_api, entry=mock_config_entry
    )

    vehicle_no_pos = Vehicle(
        id="12345",
        name="Test Vehicle",
        position=None,  # No position data
        external_voltage=12.5,
        battery_voltage=3.7,
        gps_quality=1.2,
        imei="123456789012345",
        model="Autoskope",
    )

    coordinator.data = {"12345": vehicle_no_pos}

    tracker = AutoskopeDeviceTracker(coordinator, "12345")

    # Test that longitude returns None when no position
    assert tracker.longitude is None
    assert tracker.latitude is None

    # Also test through HA integration
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = [vehicle_no_pos]

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("device_tracker.test_vehicle")
        assert state is not None
        # Both latitude and longitude should be None
        assert state.attributes.get("latitude") is None
        assert state.attributes.get("longitude") is None
