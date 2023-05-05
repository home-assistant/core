"""Blebox sensors tests."""
import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.sensor import SensorDeviceClass
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
    return (feature, "sensor.airsensor_0_air")


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
    return (feature, "sensor.tempsensor_0_temperature")


async def test_init(tempsensor, hass: HomeAssistant) -> None:
    """Test sensor default state."""

    _, entity_id = tempsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-tempSensor-1afe34db9437-0.temperature"

    state = hass.states.get(entity_id)
    assert state.name == "tempSensor-0.temperature"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.state == STATE_UNKNOWN

    device_registry = dr.async_get(hass)
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


async def test_airsensor_init(airsensor, hass: HomeAssistant) -> None:
    """Test airSensor default state."""

    _, entity_id = airsensor
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-airSensor-1afe34db9437-0.air"

    state = hass.states.get(entity_id)
    assert state.name == "airSensor-0.air"

    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.PM1
    assert state.state == STATE_UNKNOWN

    device_registry = dr.async_get(hass)
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
