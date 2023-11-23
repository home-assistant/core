"""BleBox climate entities tests."""
import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import async_setup_entity, mock_feature


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
        mode=None,
        hvac_action=None,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My sauna")
    type(product).model = PropertyMock(return_value="saunaBox")
    return (feature, "climate.saunabox_thermostat")


@pytest.fixture(name="thermobox")
def thermobox_fixture():
    """Return a default climate entity mock."""
    feature = mock_feature(
        "climates",
        blebox_uniapi.climate.Climate,
        unique_id="BleBox-thermoBox-1afe34db9437-thermostat",
        full_name="thermoBox-thermostat",
        device_class=None,
        is_on=None,
        desired=None,
        current=None,
        min_temp=-54.3,
        max_temp=124.3,
        mode=2,
        hvac_action=1,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My thermo")
    type(product).model = PropertyMock(return_value="thermoBox")
    return (feature, "climate.thermobox_thermostat")


async def test_init(
    saunabox, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test default state."""

    _, entity_id = saunabox
    entry = await async_setup_entity(hass, entity_id)
    assert entry.unique_id == "BleBox-saunaBox-1afe34db9437-thermostat"

    state = hass.states.get(entity_id)
    assert state.name == "saunaBox-thermostat"

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & ClimateEntityFeature.TARGET_TEMPERATURE

    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.OFF, None]

    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_HVAC_MODE not in state.attributes
    assert ATTR_HVAC_ACTION not in state.attributes

    assert state.attributes[ATTR_MIN_TEMP] == -54.3
    assert state.attributes[ATTR_MAX_TEMP] == 124.3
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None

    assert state.state == STATE_UNKNOWN

    device = device_registry.async_get(entry.device_id)

    assert device.name == "My sauna"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "saunaBox"
    assert device.sw_version == "1.23"


async def test_update(saunabox, hass: HomeAssistant, config) -> None:
    """Test updating."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = False
        feature_mock.desired = 64.3
        feature_mock.current = 40.9

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 64.3
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 40.9
    assert state.state == HVACMode.OFF


async def test_on_when_below_desired(saunabox, hass: HomeAssistant) -> None:
    """Test when temperature is below desired."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
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
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    feature_mock.async_off.assert_not_called()
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_TEMPERATURE] == 64.8
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.7
    assert state.state == HVACMode.HEAT


async def test_on_when_above_desired(saunabox, hass: HomeAssistant) -> None:
    """Test when temperature is below desired."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
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
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    feature_mock.async_off.assert_not_called()
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_TEMPERATURE] == 23.4
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 28.7
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.state == HVACMode.HEAT


async def test_off(saunabox, hass: HomeAssistant) -> None:
    """Test turning off."""

    feature_mock, entity_id = saunabox

    def initial_update():
        feature_mock.is_on = True
        feature_mock.is_heating = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)
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
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    feature_mock.async_on.assert_not_called()
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 29.8
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.7
    assert state.state == HVACMode.OFF


async def test_set_thermo(saunabox, hass: HomeAssistant) -> None:
    """Test setting thermostat."""

    feature_mock, entity_id = saunabox

    def update():
        feature_mock.is_on = False
        feature_mock.is_heating = False

    feature_mock.async_update = AsyncMock(side_effect=update)
    await async_setup_entity(hass, entity_id)
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
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.state == HVACMode.HEAT


async def test_update_failure(
    saunabox, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = saunabox
    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text


async def test_reding_hvac_actions(
    saunabox, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test hvac action for given device(mock) state."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = saunabox
    await async_setup_entity(hass, entity_id)

    def set_heating():
        feature_mock.is_on = True
        feature_mock.hvac_action = 1
        feature_mock.mode = 1

    feature_mock.async_update = AsyncMock(side_effect=set_heating)

    await hass.services.async_call(
        "climate",
        SERVICE_SET_TEMPERATURE,
        {"entity_id": entity_id, ATTR_TEMPERATURE: 43.21},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.OFF, HVACMode.HEAT]


async def test_thermo_off(
    thermobox, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test hvac action off fir given device state."""
    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = thermobox
    await async_setup_entity(hass, entity_id)

    def set_off():
        feature_mock.is_on = False
        feature_mock.hvac_action = 0

    feature_mock.async_update = AsyncMock(side_effect=set_off)

    await hass.services.async_call(
        "climate",
        SERVICE_SET_HVAC_MODE,
        {"entity_id": entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.OFF, HVACMode.COOL]
