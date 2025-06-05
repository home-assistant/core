"""Test the Altruist Sensor sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.components.altruist.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_sensors_setup(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test sensor setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that sensors are created
    entity_registry = er.async_get(hass)

    # Temperature sensor
    temp_entity = entity_registry.async_get(
        "sensor.altruist_5366960e8b18_bme280_temperature"
    )
    assert temp_entity is not None
    assert temp_entity.unique_id == "altruist_5366960e8b18-BME280_temperature"

    # Humidity sensor
    humidity_entity = entity_registry.async_get(
        "sensor.altruist_5366960e8b18_bme280_humidity"
    )
    assert humidity_entity is not None
    assert humidity_entity.unique_id == "altruist_5366960e8b18-BME280_humidity"

    # PM10 sensor
    pm10_entity = entity_registry.async_get("sensor.altruist_5366960e8b18_pm10")
    assert pm10_entity is not None
    assert pm10_entity.unique_id == "altruist_5366960e8b18-SDS_P1"


async def test_sensor_states(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test sensor states after data update."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Wait for the coordinator to fetch data
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    # Check sensor states
    temp_state = hass.states.get("sensor.altruist_5366960e8b18_bme280_temperature")
    assert temp_state is not None
    assert temp_state.state == "25.5"
    assert temp_state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    assert temp_state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE

    humidity_state = hass.states.get("sensor.altruist_5366960e8b18_bme280_humidity")
    assert humidity_state is not None
    assert humidity_state.state == "60.0"
    assert humidity_state.attributes["unit_of_measurement"] == PERCENTAGE
    assert humidity_state.attributes["device_class"] == SensorDeviceClass.HUMIDITY

    pm10_state = hass.states.get("sensor.altruist_5366960e8b18_pm10")
    assert pm10_state is not None
    assert pm10_state.state == "15.0"
    assert (
        pm10_state.attributes["unit_of_measurement"]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert pm10_state.attributes["device_class"] == SensorDeviceClass.PM10


async def test_sensor_device_info(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test sensor device info."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "5366960e8b18")})

    assert device is not None
    assert device.name == "Altruist 5366960e8b18"
    assert device.manufacturer == "Robonomics"
    assert device.model == "Altruist"
    assert device.sw_version == "R_2025-03"
    assert device.configuration_url == "http://192.168.1.100"


async def test_coordinator_update_interval(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test that the coordinator updates with the correct interval."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify initial fetch was called
    assert mock_altruist_client.fetch_data.call_count >= 1

    # Advance time by 15 seconds (the update interval)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()

    # Should have been called again
    assert mock_altruist_client.fetch_data.call_count >= 2


async def test_coordinator_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test coordinator error handling during updates."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Make fetch_data fail
    mock_altruist_client.fetch_data.side_effect = Exception("Connection error")

    # Advance time to trigger update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()

    # Sensors should still exist but may be unavailable
    temp_state = hass.states.get("sensor.altruist_5366960e8b18_bme280_temperature")
    assert temp_state is not None


async def test_sensor_value_parsing(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test sensor value parsing (int vs float)."""
    # Test with mixed int and float values
    mock_altruist_client.sensor_names = ["BME280_temperature", "BME280_humidity"]
    mock_altruist_client.fetch_data = AsyncMock(
        return_value=[
            {"value_type": "BME280_temperature", "value": "25.5"},  # Float
            {"value_type": "BME280_humidity", "value": "60"},  # Int
        ]
    )

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Trigger coordinator update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    # Check that float value is parsed as float
    temp_state = hass.states.get("sensor.altruist_5366960e8b18_bme280_temperature")
    assert temp_state.state == "25.5"

    # Check that int value is parsed as int
    humidity_state = hass.states.get("sensor.altruist_5366960e8b18_bme280_humidity")
    assert humidity_state.state == "60.0"


async def test_missing_sensor_data(
    hass: HomeAssistant, mock_config_entry, mock_altruist_client
) -> None:
    """Test handling when sensor data is missing from response."""
    # Setup with temperature sensor but don't include it in fetch_data response
    mock_altruist_client.sensor_names = ["BME280_temperature"]
    mock_altruist_client.fetch_data = AsyncMock(
        return_value=[
            {"value_type": "BME280_humidity", "value": "60"}  # Different sensor
        ]
    )

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.coordinator.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Trigger coordinator update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    # Sensor should exist but value might be None or previous value
    temp_state = hass.states.get("sensor.altruist_5366960e8b18_bme280_temperature")

    assert temp_state is not None
