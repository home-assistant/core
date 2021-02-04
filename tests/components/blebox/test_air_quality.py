"""Blebox air_quality tests."""

import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.air_quality import ATTR_PM_0_1, ATTR_PM_2_5, ATTR_PM_10
from homeassistant.const import ATTR_ICON, STATE_UNKNOWN

from .conftest import async_setup_entity, mock_feature


@pytest.fixture(name="airsensor")
def airsensor_fixture():
    """Return a default air quality fixture."""
    feature = mock_feature(
        "air_qualities",
        blebox_uniapi.air_quality.AirQuality,
        unique_id="BleBox-airSensor-1afe34db9437-0.air",
        full_name="airSensor-0.air",
        device_class=None,
        pm1=None,
        pm2_5=None,
        pm10=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My air sensor")
    type(product).model = PropertyMock(return_value="airSensor")
    return (feature, "air_quality.airsensor_0_air")


async def test_init(airsensor, hass, config):
    """Test airSensor default state."""

    _, entity_id = airsensor
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-airSensor-1afe34db9437-0.air"

    state = hass.states.get(entity_id)
    assert state.name == "airSensor-0.air"

    assert ATTR_PM_0_1 not in state.attributes
    assert ATTR_PM_2_5 not in state.attributes
    assert ATTR_PM_10 not in state.attributes

    assert state.attributes[ATTR_ICON] == "mdi:blur"

    assert state.state == STATE_UNKNOWN

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My air sensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "airSensor"
    assert device.sw_version == "1.23"


async def test_update(airsensor, hass, config):
    """Test air quality sensor state after update."""

    feature_mock, entity_id = airsensor

    def initial_update():
        feature_mock.pm1 = 49
        feature_mock.pm2_5 = 222
        feature_mock.pm10 = 333

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_PM_0_1] == 49
    assert state.attributes[ATTR_PM_2_5] == 222
    assert state.attributes[ATTR_PM_10] == 333

    assert state.state == "222"


async def test_update_failure(airsensor, hass, config, caplog):
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = airsensor
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, config, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text
