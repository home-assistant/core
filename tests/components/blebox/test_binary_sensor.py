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
        index=None,
    )
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My rain sensor")
    type(product).model = PropertyMock(return_value="rainSensor")
    return feature, "binary_sensor.my_rain_sensor_moisture"


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
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My open sensor")
    type(product).model = PropertyMock(return_value="openSensor")
    return feature, "binary_sensor.my_open_sensor_window"


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
    type(feature).name = PropertyMock(return_value=None)
    product = feature.product
    type(product).name = PropertyMock(return_value="My input sensor")
    type(product).model = PropertyMock(return_value="inputSensorD")
    return feature, "binary_sensor.my_input_sensor_input"


@pytest.mark.parametrize(
    (
        "fixture_name",
        "unique_id",
        "expected_name",
        "expected_device_class",
        "expected_state",
        "expected_device_name",
    ),
    [
        pytest.param(
            "rainsensor",
            "BleBox-windRainSensor-ea68e74f4f49-0.rain",
            "My rain sensor Moisture",
            BinarySensorDeviceClass.MOISTURE,
            STATE_ON,
            "My rain sensor",
            id="moisture",
        ),
        pytest.param(
            "inputsensor",
            "BleBox-inputSensorD-aa11bb22cc33-0.input",
            "My input sensor Input",
            None,
            STATE_ON,
            "My input sensor",
            id="input",
        ),
    ],
)
async def test_init(
    hass: HomeAssistant,
    fixture_name: str,
    unique_id: str,
    expected_name: str,
    expected_device_class: BinarySensorDeviceClass | None,
    expected_state: str,
    expected_device_name: str,
    device_registry: dr.DeviceRegistry,
    request: pytest.FixtureRequest,
) -> None:
    """Test binary_sensor initialisation."""
    _, entity_id = request.getfixturevalue(fixture_name)
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state.name == expected_name
    assert state.attributes.get(ATTR_DEVICE_CLASS) == expected_device_class
    assert state.state == expected_state

    device = device_registry.async_get(entry.device_id)
    assert device.name == expected_device_name


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
    assert state.name == "My open sensor Window"
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
