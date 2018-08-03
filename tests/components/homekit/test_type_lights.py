"""Test different accessory types: Lights."""
from collections import namedtuple

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT, ATTR_COLOR_TEMP, ATTR_HS_COLOR,
    DOMAIN, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES,
    STATE_ON, STATE_OFF, STATE_UNKNOWN)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope='module')
def cls():
    """Patch debounce decorator during import of type_lights."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_lights',
                         fromlist=['Light'])
    patcher_tuple = namedtuple('Cls', ['light'])
    yield patcher_tuple(light=_import.Light)
    patcher.stop()


async def test_light_basic(hass, hk_driver, cls):
    """Test light with char state."""
    entity_id = 'light.demo'

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, 'Light', entity_id, 2, None)

    assert acc.aid == 2
    assert acc.category == 5  # Lightbulb
    assert acc.char_on.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN, 'turn_off')

    await hass.async_add_job(acc.char_on.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await hass.async_add_job(acc.char_on.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_light_brightness(hass, hk_driver, cls):
    """Test light with brightness."""
    entity_id = 'light.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_BRIGHTNESS, ATTR_BRIGHTNESS: 255})
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, 'Light', entity_id, 2, None)

    assert acc.char_brightness.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 100

    hass.states.async_set(entity_id, STATE_ON, {ATTR_BRIGHTNESS: 102})
    await hass.async_block_till_done()
    assert acc.char_brightness.value == 40

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN, 'turn_off')

    await hass.async_add_job(acc.char_brightness.client_update_value, 20)
    await hass.async_add_job(acc.char_on.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on[0]
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_BRIGHTNESS_PCT] == 20

    await hass.async_add_job(acc.char_on.client_update_value, 1)
    await hass.async_add_job(acc.char_brightness.client_update_value, 40)
    await hass.async_block_till_done()
    assert call_turn_on[1]
    assert call_turn_on[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[1].data[ATTR_BRIGHTNESS_PCT] == 40

    await hass.async_add_job(acc.char_on.client_update_value, 1)
    await hass.async_add_job(acc.char_brightness.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_light_color_temperature(hass, hk_driver, cls):
    """Test light with color temperature."""
    entity_id = 'light.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_COLOR_TEMP,
        ATTR_COLOR_TEMP: 190})
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, 'Light', entity_id, 2, None)

    assert acc.char_color_temperature.value == 153

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_color_temperature.value == 190

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')

    await hass.async_add_job(
        acc.char_color_temperature.client_update_value, 250)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_COLOR_TEMP] == 250


async def test_light_rgb_color(hass, hk_driver, cls):
    """Test light with rgb_color."""
    entity_id = 'light.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_COLOR,
        ATTR_HS_COLOR: (260, 90)})
    await hass.async_block_till_done()
    acc = cls.light(hass, hk_driver, 'Light', entity_id, 2, None)

    assert acc.char_hue.value == 0
    assert acc.char_saturation.value == 75

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_hue.value == 260
    assert acc.char_saturation.value == 90

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')

    await hass.async_add_job(acc.char_hue.client_update_value, 145)
    await hass.async_add_job(acc.char_saturation.client_update_value, 75)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_turn_on[0].data[ATTR_HS_COLOR] == (145, 75)
