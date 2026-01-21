"""Tests for the Autoskope binary sensor platform."""

from unittest.mock import patch

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
    mock_vehicles_list,
) -> None:
    """Test binary sensor setup."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that binary sensor is created
        assert hass.states.get("binary_sensor.test_vehicle_motion") is not None


async def test_park_mode_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
    mock_vehicle_with_position,
) -> None:
    """Test park mode binary sensor states."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        # Test with park_mode = False (vehicle is moving, motion detected)
        mock_vehicle_with_position.position.park_mode = False
        mock_autoskope_api.get_vehicles.return_value = [mock_vehicle_with_position]

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        motion_sensor = hass.states.get("binary_sensor.test_vehicle_motion")
        assert motion_sensor is not None
        assert motion_sensor.state == STATE_ON  # Motion detected (not parked)

        # Update to park_mode = True (vehicle is parked, no motion)
        mock_vehicle_with_position.position.park_mode = True
        mock_autoskope_api.get_vehicles.return_value = [mock_vehicle_with_position]

        # Trigger coordinator update via config entry runtime_data
        coordinator = mock_config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        motion_sensor = hass.states.get("binary_sensor.test_vehicle_motion")
        assert motion_sensor.state == STATE_OFF  # No motion (parked)


async def test_binary_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test binary sensor becomes unavailable when no data."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = []
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Binary sensor should not exist when no vehicles
        assert hass.states.get("binary_sensor.test_vehicle_motion") is None


async def test_binary_sensor_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
    mock_vehicles_list,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor entity is registered correctly."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check entity registry
        motion_entry = entity_registry.async_get("binary_sensor.test_vehicle_motion")
        assert motion_entry is not None
        assert motion_entry.unique_id == "12345_park_mode"
        assert motion_entry.translation_key == "park_mode"
