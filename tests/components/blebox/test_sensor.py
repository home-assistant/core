"""Blebox sensors tests."""

import logging

import blebox_uniapi
import pytest

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_TEMPERATURE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)

from .conftest import async_setup_entity, mock_feature

from tests.async_mock import AsyncMock, PropertyMock


@pytest.fixture(name="tempsensor")
def tempsensor_fixture():
    """Return a default sensor mock."""
    feature = mock_feature(
        "sensors",
        blebox_uniapi.sensor.Temperature,
        unique_id="BleBox-tempSensor-1afe34db9437-0.temperature",
        full_name="tempSensor-0.temperature",
        device_class="temperature",
        unit="celsius",
        current=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My temperature sensor")
    type(product).model = PropertyMock(return_value="tempSensor")
    return (feature, "sensor.tempsensor_0_temperature")


async def test_init(tempsensor, hass, config):
    """Test sensor default state."""

    _, entity_id = tempsensor
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-tempSensor-1afe34db9437-0.temperature"

    state = hass.states.get(entity_id)
    assert state.name == "tempSensor-0.temperature"

    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert state.state == STATE_UNKNOWN

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My temperature sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "tempSensor"
    assert device.sw_version == "1.23"


async def test_update(tempsensor, hass, config):
    """Test sensor update."""

    feature_mock, entity_id = tempsensor

    def initial_update():
        feature_mock.current = 25.18

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert state.state == "25.18"


async def test_update_failure(tempsensor, hass, config, caplog):
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = tempsensor
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, config, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text
