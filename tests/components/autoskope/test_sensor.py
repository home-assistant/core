"""Tests for the Autoskope sensor platform."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
    mock_vehicles_list,
) -> None:
    """Test sensor setup."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that sensors are created
        assert hass.states.get("sensor.test_vehicle_battery_voltage") is not None
        assert hass.states.get("sensor.test_vehicle_external_voltage") is not None
        assert hass.states.get("sensor.test_vehicle_speed") is not None
        assert hass.states.get("sensor.test_vehicle_gps_quality") is not None
        assert hass.states.get("sensor.test_vehicle_gps_accuracy") is not None


async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
    mock_vehicles_list,
) -> None:
    """Test sensor values."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check sensor values
        battery_voltage = hass.states.get("sensor.test_vehicle_battery_voltage")
        assert battery_voltage is not None
        assert battery_voltage.state == "3.7"

        external_voltage = hass.states.get("sensor.test_vehicle_external_voltage")
        assert external_voltage is not None
        assert external_voltage.state == "12.5"

        speed = hass.states.get("sensor.test_vehicle_speed")
        assert speed is not None
        assert speed.state == "0.0"

        gps_quality = hass.states.get("sensor.test_vehicle_gps_quality")
        assert gps_quality is not None
        assert gps_quality.state == "1.2"

        gps_accuracy = hass.states.get("sensor.test_vehicle_gps_accuracy")
        assert gps_accuracy is not None
        assert gps_accuracy.state == "6"  # max(5, int(1.2 * 5.0)) = 6


async def test_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
) -> None:
    """Test sensor becomes unavailable when no data."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = []
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # All sensors should be unavailable
        assert hass.states.get("sensor.test_vehicle_battery_voltage") is None


async def test_sensor_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_api,
    mock_vehicles_list,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor entities are registered correctly."""
    with patch(
        "homeassistant.components.autoskope.AutoskopeApi",
        return_value=mock_autoskope_api,
    ):
        mock_autoskope_api.get_vehicles.return_value = mock_vehicles_list
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check entity registry
        battery_entry = entity_registry.async_get("sensor.test_vehicle_battery_voltage")
        assert battery_entry is not None
        assert battery_entry.unique_id == "12345_battery_voltage"
        assert battery_entry.translation_key == "battery_voltage"

        speed_entry = entity_registry.async_get("sensor.test_vehicle_speed")
        assert speed_entry is not None
        assert speed_entry.unique_id == "12345_speed"
        assert speed_entry.translation_key == "speed"
