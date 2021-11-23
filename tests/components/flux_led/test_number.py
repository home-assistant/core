"""Tests for the flux_led number platform."""


from flux_led.const import COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB
import pytest

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mocked_bulb,
    _patch_discovery,
    _patch_wifibulb,
    async_mock_device_turn_off,
    async_mock_device_turn_on,
    async_mock_effect_speed,
)

from tests.common import MockConfigEntry


async def test_number_unique_id(hass: HomeAssistant) -> None:
    """Test a number unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "number.rgbw_controller_ddeeff_effect_speed"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS


async def test_rgb_light_effect_speed(hass: HomeAssistant) -> None:
    """Test an rgb light with an effect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(model_num=0x33)  # RGB only model

    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB

    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    await async_mock_device_turn_on(hass, bulb)

    light_entity_id = "light.rgbw_controller_ddeeff"
    number_entity_id = "number.rgbw_controller_ddeeff_effect_speed"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 100},
            blocking=True,
        )

    state = hass.states.get(light_entity_id)
    assert state.state == STATE_ON

    bulb.effect = "colorloop"
    bulb.speed = 50
    await async_mock_device_turn_off(hass, bulb)
    state = hass.states.get(number_entity_id)
    assert state.state == "50"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 100},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("colorloop", 100)
    bulb.async_set_effect.reset_mock()

    await async_mock_effect_speed(hass, bulb, "red_fade", 50)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 50},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("red_fade", 50)
    bulb.async_set_effect.reset_mock()

    state = hass.states.get(number_entity_id)
    assert state.state == "50"


async def test_original_addressable_light_effect_speed(hass: HomeAssistant) -> None:
    """Test an original addressable light with an effect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.original_addressable = True
    bulb.raw_state = bulb.raw_state._replace(
        model_num=0xA1
    )  # Original addressable model
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    bulb.effect = "7 colors change gradually"
    bulb.speed = 50
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    await async_mock_device_turn_on(hass, bulb)

    light_entity_id = "light.rgbw_controller_ddeeff"
    number_entity_id = "number.rgbw_controller_ddeeff_effect_speed"

    state = hass.states.get(light_entity_id)
    assert state.state == STATE_ON

    state = hass.states.get(number_entity_id)
    assert state.state == "50"

    await async_mock_device_turn_off(hass, bulb)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 100},
            blocking=True,
        )

    await async_mock_device_turn_on(hass, bulb)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 100},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("7 colors change gradually", 100)
    bulb.async_set_effect.reset_mock()
    await async_mock_effect_speed(hass, bulb, "7 colors run in olivary", 100)

    state = hass.states.get(number_entity_id)
    assert state.state == "100"


async def test_addressable_light_effect_speed(hass: HomeAssistant) -> None:
    """Test an addressable light with an effect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.addressable = True
    bulb.raw_state = bulb.raw_state._replace(
        model_num=0xA2
    )  # Original addressable model
    bulb.color_modes = {FLUX_COLOR_MODE_RGB}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    bulb.effect = "RBM 1"
    bulb.speed = 50
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    await async_mock_device_turn_on(hass, bulb)

    light_entity_id = "light.rgbw_controller_ddeeff"
    number_entity_id = "number.rgbw_controller_ddeeff_effect_speed"

    state = hass.states.get(light_entity_id)
    assert state.state == STATE_ON

    state = hass.states.get(number_entity_id)
    assert state.state == "50"

    await async_mock_device_turn_off(hass, bulb)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 100},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("RBM 1", 100)
    bulb.async_set_effect.reset_mock()

    await async_mock_device_turn_on(hass, bulb)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: number_entity_id, ATTR_VALUE: 100},
        blocking=True,
    )
    bulb.async_set_effect.assert_called_with("RBM 1", 100)
    bulb.async_set_effect.reset_mock()
    await async_mock_effect_speed(hass, bulb, "RBM 2", 100)

    state = hass.states.get(number_entity_id)
    assert state.state == "100"
