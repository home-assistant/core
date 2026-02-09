"""Tests for the BACnet sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    state = hass.states.get("sensor.test_hvac_controller_outside_air_temperature")
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
    """Test that multi-state sensors show text from stateText mapping."""
    await init_integration(hass)

    # Operating Mode (multi-state-input,0) - value 2 maps to "Heating"
    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state is not None
    assert state.state == "Heating"
    assert state.attributes.get("device_class") == SensorDeviceClass.ENUM
    assert state.attributes.get("options") == ["Off", "Heating", "Cooling", "Auto"]


async def test_sensor_count(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test the correct number of sensors are created."""
    await init_integration(hass)

    sensor_states = hass.states.async_entity_ids("sensor")
    # We expect 5 sensors:
    # analog-input,0 (Zone Temp), analog-input,1 (OAT), analog-input,2 (Humidity),
    # analog-value,0 (Setpoint), multi-state-input,0 (Operating Mode)
    assert len(sensor_states) == 5


async def test_device_info_no_suggested_area(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that device_info does not include suggested_area."""
    await init_integration(hass)

    # Get entity registry and pick a sensor
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("sensor.test_hvac_controller_zone_temperature")
    assert entity is not None

    # Get device registry and check the device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity.device_id)
    assert device is not None

    # If suggested_area was set during device creation, it would populate area_id.
    # Verify no area was assigned (meaning no suggested_area in device_info).
    assert device.area_id is None
