"""Blebox sensors tests."""

import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.blebox.const import OPEN_STATUS
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import async_setup_entity, mock_feature


@pytest.fixture(name="airsensor")
def airsensor_fixture():
    """Return a default AirQuality sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.AirQuality,
        unique_id="BleBox-airSensor-1afe34db9437-0.air",
        full_name="airSensor-0.air",
        device_class="pm1",
        unit="concentration_of_mp",
        native_value=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My air sensor")
    type(product).model = PropertyMock(return_value="airSensor")
    return (feature, "sensor.my_air_sensor_airsensor_0_air")


@pytest.fixture(name="tempsensor")
def tempsensor_fixture():
    """Return a default Temperature sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.Temperature,
        unique_id="BleBox-tempSensor-1afe34db9437-0.temperature",
        full_name="tempSensor-0.temperature",
        device_class="temperature",
        unit="celsius",
        current=None,
        native_value=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My temperature sensor")
    type(product).model = PropertyMock(return_value="tempSensor")
    return (feature, "sensor.my_temperature_sensor_tempsensor_0_temperature")


async def test_init(
    tempsensor, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test sensor default state."""

    _, entity_id = tempsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-tempSensor-1afe34db9437-0.temperature"

    state = hass.states.get(entity_id)
    assert state.name == "My temperature sensor tempSensor-0.temperature"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My temperature sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "tempSensor"
    assert device.sw_version == "1.23"


async def test_update(tempsensor, hass: HomeAssistant) -> None:
    """Test sensor update."""

    feature_mock, entity_id = tempsensor

    def initial_update():
        feature_mock.native_value = 25.18

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.state == "25.18"


async def test_update_failure(
    tempsensor, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = tempsensor
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text


async def test_airsensor_init(
    airsensor, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test airSensor default state."""

    _, entity_id = airsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-airSensor-1afe34db9437-0.air"

    state = hass.states.get(entity_id)
    assert state.name == "My air sensor airSensor-0.air"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.PM1
    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My air sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "airSensor"
    assert device.sw_version == "1.23"


async def test_airsensor_update(airsensor, hass: HomeAssistant) -> None:
    """Test air quality sensor state after update."""

    feature_mock, entity_id = airsensor

    def initial_update():
        feature_mock.native_value = 49

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    assert state.state == "49"


@pytest.fixture(name="open_status_sensor")
def open_status_sensor_fixture():
    """Return a default openStatus sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.GenericSensor,
        unique_id="BleBox-openSensor-1afe34db9437-0.openStatus",
        full_name="openSensor-0.openStatus",
        device_class="openStatus",
        native_value=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My open sensor")
    type(product).model = PropertyMock(return_value="openSensor")
    return (feature, "sensor.my_open_sensor_opensensor_0_openstatus")


async def test_open_status_sensor_init(open_status_sensor, hass: HomeAssistant) -> None:
    """Test openStatus sensor initial state is unknown."""
    _, entity_id = open_status_sensor
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == list(OPEN_STATUS.values())
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(0, "open", id="0_open"),
        pytest.param(1, "unclosed_or_unlocked", id="1_unclosed_or_unlocked"),
        pytest.param(2, "ajar", id="2_ajar"),
        pytest.param(3, "closed_but_unlocked", id="3_closed_but_unlocked"),
        pytest.param(4, "closed", id="4_closed"),
    ],
)
async def test_open_status_sensor_value_mapping(
    open_status_sensor,
    hass: HomeAssistant,
    raw_value: int,
    expected_state: str,
) -> None:
    """Test that each raw numeric openStatus value maps to the correct string state."""
    feature_mock, entity_id = open_status_sensor

    def set_value():
        feature_mock.native_value = raw_value

    feature_mock.async_update = AsyncMock(side_effect=set_value)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == expected_state
    assert state.state in OPEN_STATUS.values()


async def test_open_status_sensor_none_value(
    open_status_sensor, hass: HomeAssistant
) -> None:
    """Test that a None native_value yields an unknown state."""
    feature_mock, entity_id = open_status_sensor

    def set_none():
        feature_mock.native_value = None

    feature_mock.async_update = AsyncMock(side_effect=set_none)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
