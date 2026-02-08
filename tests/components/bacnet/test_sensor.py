"""Tests for the BACnet sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_analog_sensors_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that analog sensors are created for analog BACnet objects."""
    await init_integration(hass)

    # Zone Temperature (analog-input,0) - 72.5°F converted to °C by HA
    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert float(state.state) == 22.5

    # Outside Air Temperature (analog-input,1) - 55.0°F converted to °C
    state = hass.states.get(
        "sensor.test_hvac_controller_outside_air_temperature"
    )
    assert state is not None
    # 55°F = 12.7778°C (HA stores the full precision)
    assert abs(float(state.state) - 12.7778) < 0.01

    # Zone Humidity (analog-input,2) - 45% stays as 45%
    state = hass.states.get("sensor.test_hvac_controller_zone_humidity")
    assert state is not None
    assert state.state == "45.0"


async def test_analog_sensor_device_class(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that BACnet units map to correct device classes."""
    await init_integration(hass)

    # Temperature sensor should have temperature device class
    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE

    # Humidity sensor should have humidity device class
    state = hass.states.get("sensor.test_hvac_controller_zone_humidity")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.HUMIDITY
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_multistate_sensor_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that multi-state sensors are created."""
    await init_integration(hass)

    # Operating Mode (multi-state-input,0)
    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state is not None
    assert state.state == "2"


async def test_analog_output_sensor(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that analog output objects create sensors."""
    await init_integration(hass)

    # Heating Valve (analog-output,0) - 75% stays as 75%
    state = hass.states.get("sensor.test_hvac_controller_heating_valve")
    assert state is not None
    assert state.state == "75.0"
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_sensor_count(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test the correct number of sensors are created."""
    await init_integration(hass)

    sensor_states = hass.states.async_entity_ids("sensor")
    # We expect 6 sensors:
    # analog-input,0 (Zone Temp), analog-input,1 (OAT), analog-input,2 (Humidity),
    # analog-output,0 (Heating Valve), analog-value,0 (Setpoint),
    # multi-state-input,0 (Operating Mode)
    assert len(sensor_states) == 6


async def test_device_info_no_suggested_area(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that device_info does not include suggested_area."""
    from homeassistant.helpers import entity_registry as er, device_registry as dr

    await init_integration(hass)

    # Get entity registry and pick a sensor
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("sensor.test_hvac_controller_zone_temperature")
    assert entity is not None

    # Get device registry and check the device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity.device_id)
    assert device is not None

    # Verify suggested_area is not in the device info
    # Note: The device object doesn't expose suggested_area directly,
    # but if it was set during creation, it would show up in the device's area_id
    # For this test, we're verifying the entity's device_info attribute
    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None

    # Get the coordinator to access the entity
    from homeassistant.components.bacnet import DOMAIN

    entries = hass.config_entries.async_entries(DOMAIN)
    device_entry = [e for e in entries if e.data.get("entry_type") == "device"][0]
    coordinator = device_entry.runtime_data.coordinator

    # Find the entity in the platforms
    from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

    for entity_id, entity in hass.data["entity_platform"][SENSOR_DOMAIN].items():
        if hasattr(entity, "_attr_device_info"):
            # Verify suggested_area is not in device_info
            assert "suggested_area" not in entity._attr_device_info
            break
