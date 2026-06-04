"""Blebox binary_sensor entities test."""

from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
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
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My rain sensor")
    type(product).model = PropertyMock(return_value="rainSensor")
    return feature, "binary_sensor.my_rain_sensor_windrainsensor_0_rain"


@pytest.fixture(name="open_sensor")
def open_sensor_fixture() -> tuple[AsyncMock, str]:
    """Return a default open/window binary sensor fixture."""
    feature: AsyncMock = mock_feature(
        "binary_sensors",
        blebox_uniapi.binary_sensor.Open,
        unique_id="BleBox-openSensor-1afe34db9437-0.open",
        full_name="openSensor-0.open",
        device_class="open",
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My open sensor")
    type(product).model = PropertyMock(return_value="openSensor")
    return feature, "binary_sensor.my_open_sensor_opensensor_0_open"


async def test_init(
    rainsensor: AsyncMock, device_registry: dr.DeviceRegistry, hass: HomeAssistant
) -> None:
    """Test binary_sensor initialisation."""
    _, entity_id = rainsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-windRainSensor-ea68e74f4f49-0.rain"

    state = hass.states.get(entity_id)
    assert state.name == "My rain sensor windRainSensor-0.rain"

    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOISTURE
    assert state.state == STATE_ON

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My rain sensor"


async def test_open_sensor_init(
    open_sensor: tuple[AsyncMock, str],
    device_registry: dr.DeviceRegistry,
    hass: HomeAssistant,
) -> None:
    """Test open/window binary sensor initialisation."""
    _, entity_id = open_sensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-openSensor-1afe34db9437-0.open"

    state = hass.states.get(entity_id)
    assert state.name == "My open sensor openSensor-0.open"
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.WINDOW

    device = device_registry.async_get(entry.device_id)
    assert device.name == "My open sensor"
    assert device.model == "openSensor"


@pytest.mark.parametrize(
    ("is_open", "expected_state"),
    [
        pytest.param(True, STATE_ON, id="open"),
        pytest.param(False, STATE_OFF, id="closed"),
    ],
)
async def test_open_sensor_state(
    open_sensor: tuple[AsyncMock, str],
    hass: HomeAssistant,
    is_open: bool,
    expected_state: str,
) -> None:
    """Test open/window binary sensor reports open and closed states correctly."""
    feature_mock, entity_id = open_sensor
    feature_mock.state = is_open
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == expected_state
