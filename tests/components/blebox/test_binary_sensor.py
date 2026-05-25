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
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My rain sensor")
    type(product).model = PropertyMock(return_value="rainSensor")
    return feature, "binary_sensor.my_rain_sensor_windrainsensor_0_rain"


@pytest.fixture(name="inputsensor")
def inputsensor_fixture() -> tuple[AsyncMock, str]:
    """Return a default inputSensor fixture."""
    feature: AsyncMock = mock_feature(
        "binary_sensors",
        blebox_uniapi.binary_sensor.Input,
        unique_id="BleBox-inputSensorD-aa11bb22cc33-0.input",
        full_name="inputSensorD-0.input",
        device_class="input",
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My input sensor")
    type(product).model = PropertyMock(return_value="inputSensorD")
    return feature, "binary_sensor.my_input_sensor_inputsensord_0_input"


@pytest.mark.parametrize(
    (
        "fixture_name",
        "entity_id",
        "unique_id",
        "expected_name",
        "expected_device_class",
        "expected_state",
    ),
    [
        pytest.param(
            "rainsensor",
            "binary_sensor.my_rain_sensor_windrainsensor_0_rain",
            "BleBox-windRainSensor-ea68e74f4f49-0.rain",
            "My rain sensor windRainSensor-0.rain",
            BinarySensorDeviceClass.MOISTURE,
            STATE_ON,
            id="moisture",
        ),
        pytest.param(
            "inputsensor",
            "binary_sensor.my_input_sensor_inputsensord_0_input",
            "BleBox-inputSensorD-aa11bb22cc33-0.input",
            "My input sensor inputSensorD-0.input",
            None,
            STATE_ON,
            id="input",
        ),
    ],
)
async def test_init(
    fixture_name: str,
    entity_id: str,
    unique_id: str,
    expected_name: str,
    expected_device_class: BinarySensorDeviceClass | None,
    expected_state: str,
    device_registry: dr.DeviceRegistry,
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
) -> None:
    """Test binary_sensor initialisation."""
    request.getfixturevalue(fixture_name)
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state.name == expected_name
    assert state.attributes.get(ATTR_DEVICE_CLASS) == expected_device_class
    assert state.state == expected_state

    device = device_registry.async_get(entry.device_id)
    assert device is not None
