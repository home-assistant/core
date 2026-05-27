"""Tests for the ALLNET sensor platform."""

import pytest

from homeassistant.components.allnet.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_sensor_entities_created(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensor entities are created for SENSOR channels."""
    # temp_0, current_0, humidity_0 (all kind=SENSOR)
    state_temp = hass.states.get("sensor.allnet_test_device_temperature")
    state_current = hass.states.get("sensor.allnet_test_device_current")
    state_humidity = hass.states.get("sensor.allnet_test_device_humidity")

    assert state_temp is not None
    assert state_current is not None
    assert state_humidity is not None


@pytest.mark.asyncio
async def test_sensor_native_value(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensor native_value is set from channel.value."""
    state = hass.states.get("sensor.allnet_test_device_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(22.5)


@pytest.mark.asyncio
async def test_sensor_temperature_device_class(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that °C unit maps to TEMPERATURE device class."""
    state = hass.states.get("sensor.allnet_test_device_temperature")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS


@pytest.mark.asyncio
async def test_sensor_current_device_class(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that A unit maps to CURRENT device class."""
    state = hass.states.get("sensor.allnet_test_device_current")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.CURRENT
    assert state.attributes.get("unit_of_measurement") == UnitOfElectricCurrent.AMPERE


@pytest.mark.asyncio
async def test_sensor_humidity_device_class(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that % unit maps to HUMIDITY device class."""
    state = hass.states.get("sensor.allnet_test_device_humidity")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_sensor_unavailable_when_value_none(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensors with value=None are marked unavailable."""
    state = hass.states.get("sensor.allnet_test_device_humidity")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_sensor_unique_id(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that sensor entities have the correct unique_id."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{TEST_UNIQUE_ID}_temp_0_sensor"
    )
    assert entry is not None


@pytest.mark.asyncio
async def test_sensor_no_binary_sensors_in_sensor_platform(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that binary_sensor channels don't appear as sensor entities."""
    state = hass.states.get("sensor.allnet_test_device_door_contact")
    assert state is None
