"""Blebox binary_sensor entities test."""

from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import async_setup_entity, mock_feature


@pytest.fixture(name="rainsensor")
def airsensor_fixture() -> tuple[AsyncMock, str]:
    """Return a default air quality fixture."""
    feature: AsyncMock = mock_feature(
        "binary_sensors",
        blebox_uniapi.binary_sensor.Rain,
        unique_id="BleBox-windRainSensor-ea68e74f4f49-0.rain",
        full_name="windRainSensor-0.rain",
        device_class="moisture",
        index=None,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My rain sensor")
    type(product).model = PropertyMock(return_value="rainSensor")
    return feature, "binary_sensor.my_rain_sensor_moisture"


async def test_init(
    rainsensor: AsyncMock, device_registry: dr.DeviceRegistry, hass: HomeAssistant
) -> None:
    """Test binary_sensor initialisation."""
    _, entity_id = rainsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-windRainSensor-ea68e74f4f49-0.rain"

    state = hass.states.get(entity_id)
    assert state.name == "My rain sensor Moisture"

    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOISTURE
    assert state.state == STATE_ON

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My rain sensor"


async def test_binary_sensor_with_name(hass: HomeAssistant) -> None:
    """Test that a binary sensor with a feature name uses it as the entity name."""
    feature = mock_feature(
        "binary_sensors",
        blebox_uniapi.binary_sensor.Rain,
        unique_id="BleBox-windRainSensor-ea68e74f4f49-0.rain",
        full_name="windRainSensor-0.rain",
        device_class="moisture",
        index=0,
    )
    type(feature).name = PropertyMock(return_value="Front yard")
    product = feature.product
    type(product).name = PropertyMock(return_value="My rain sensor")
    type(product).model = PropertyMock(return_value="rainSensor")

    await async_setup_entity(hass, "binary_sensor.my_rain_sensor_front_yard")
    state = hass.states.get("binary_sensor.my_rain_sensor_front_yard")
    assert state.name == "My rain sensor Front yard"
