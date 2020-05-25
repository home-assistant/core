"""BleBox climate entities tests."""

import logging

import blebox_uniapi
import pytest

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
)

from .conftest import async_setup_entity, mock_feature

from tests.async_mock import AsyncMock, PropertyMock


@pytest.fixture(name="saunabox")
def saunabox_fixture():
    """Return a default climate entity mock."""
    feature = mock_feature(
        "climates",
        blebox_uniapi.climate.Climate,
        unique_id="BleBox-saunaBox-1afe34db9437-thermostat",
        full_name="saunaBox-thermostat",
        device_class=None,
        is_on=None,
        desired=None,
        current=None,
        min_temp=-54.3,
        max_temp=124.3,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My sauna")
    type(product).model = PropertyMock(return_value="saunaBox")
    return (feature, "climate.saunabox_thermostat")


async def test_init(saunabox, hass, config):
    """Test default state."""

    _, entity_id = saunabox
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-saunaBox-1afe34db9437-thermostat"

    state = hass.states.get(entity_id)
    assert state.name == "saunaBox-thermostat"

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_TARGET_TEMPERATURE

    assert state.attributes[ATTR_HVAC_MODES] == [HVAC_MODE_OFF, HVAC_MODE_HEAT]

    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_HVAC_MODE not in state.attributes
    assert ATTR_HVAC_ACTION not in state.attributes

    assert state.attributes[ATTR_MIN_TEMP] == -54.3
    assert state.attributes[ATTR_MAX_TEMP] == 124.3
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None

    assert state.state == STATE_UNKNOWN

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My sauna"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "saunaBox"
    assert device.sw_version == "1.23"


async def test_update(saunabox, hass, config):
    """Test updating."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = False
        feature_mock.desired = 64.3
        feature_mock.current = 40.9

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert state.attributes[ATTR_TEMPERATURE] == 64.3
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 40.9
    assert state.state == HVAC_MODE_OFF


async def test_on_when_below_desired(saunabox, hass, config):
    """Test when temperature is below desired."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    def turn_on():
        feature_mock.is_on = True
        feature_mock.is_heating = True
        feature_mock.desired = 64.8
        feature_mock.current = 25.7

    feature_mock.async_on = AsyncMock(side_effect=turn_on)
    await hass.services.async_call(
        "climate",
        SERVICE_SET_HVAC_MODE,
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 64.8
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.7
    assert state.state == HVAC_MODE_HEAT


async def test_on_when_above_desired(saunabox, hass, config):
    """Test when temperature is below desired."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    def turn_on():
        feature_mock.is_on = True
        feature_mock.is_heating = False
        feature_mock.desired = 23.4
        feature_mock.current = 28.7

    feature_mock.async_on = AsyncMock(side_effect=turn_on)

    await hass.services.async_call(
        "climate",
        SERVICE_SET_HVAC_MODE,
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_TEMPERATURE] == 23.4
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 28.7
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE
    assert state.state == HVAC_MODE_HEAT


async def test_off(saunabox, hass, config):
    """Test turning off."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = True
        feature_mock.is_heating = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    def turn_off():
        feature_mock.is_on = False
        feature_mock.is_heating = False
        feature_mock.desired = 29.8
        feature_mock.current = 22.7

    feature_mock.async_off = AsyncMock(side_effect=turn_off)
    await hass.services.async_call(
        "climate",
        SERVICE_SET_HVAC_MODE,
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF
    assert state.attributes[ATTR_TEMPERATURE] == 29.8
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.7
    assert state.state == HVAC_MODE_OFF


async def test_set_thermo(saunabox, hass, config):
    """Test setting thermostat."""

    feature_mock, entity_id = saunabox

    def update():
        feature_mock.is_on = False
        feature_mock.is_heating = False

    feature_mock.async_update = AsyncMock(side_effect=update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    def set_temp(temp):
        feature_mock.is_on = True
        feature_mock.is_heating = True
        feature_mock.desired = 29.2
        feature_mock.current = 29.1

    feature_mock.async_set_temperature = AsyncMock(side_effect=set_temp)
    await hass.services.async_call(
        "climate",
        SERVICE_SET_TEMPERATURE,
        {"entity_id": entity_id, ATTR_TEMPERATURE: 43.21},
        blocking=True,
    )
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_TEMPERATURE] == 29.2
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 29.1
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT
    assert state.state == HVAC_MODE_HEAT


async def test_update_failure(saunabox, hass, config, caplog):
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = saunabox
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, config, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text
