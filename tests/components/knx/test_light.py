"""Test KNX light."""
from __future__ import annotations

from homeassistant.components.knx.const import CONF_STATE_ADDRESS, KNX_ADDRESS
from homeassistant.components.knx.schema import LightSchema
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
)
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_light_simple(hass: HomeAssistant, knx: KNXTestKit):
    """Test simple KNX light."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    assert len(hass.states.async_all()) == 1

    knx.assert_state("light.test", STATE_OFF)
    # turn on light
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test"},
        blocking=True,
    )
    await knx.assert_write(test_address, True)
    knx.assert_state(
        "light.test",
        STATE_ON,
        {ATTR_COLOR_MODE: COLOR_MODE_ONOFF},
    )
    # turn off light
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test"},
        blocking=True,
    )
    await knx.assert_write(test_address, False)
    knx.assert_state("light.test", STATE_OFF)
    # receive ON telegram
    await knx.receive_write(test_address, True)
    knx.assert_state("light.test", STATE_ON)

    # receive OFF telegram
    await knx.receive_write(test_address, False)
    knx.assert_state("light.test", STATE_OFF)

    # switch does not respond to read by default
    await knx.receive_read(test_address)
    await knx.assert_telegram_count(0)


async def test_light_brightness(hass: HomeAssistant, knx: KNXTestKit):
    """Test dimmable KNX light."""
    test_address = "1/1/1"
    test_brightness = "1/1/2"
    test_brightness_state = "1/1/3"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
            }
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_brightness_state)
    # turn on light via brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 80},
        blocking=True,
    )
    await knx.assert_write(test_brightness, (80,))
    # state is still OFF until controller reports otherwise
    knx.assert_state("light.test", STATE_OFF)
    await knx.receive_write(test_address, True)
    knx.assert_state(
        "light.test",
        STATE_ON,
        {ATTR_BRIGHTNESS: 80, ATTR_COLOR_MODE: COLOR_MODE_BRIGHTNESS},
    )
    # receive brightness changes from KNX
    await knx.receive_write(test_brightness_state, (255,))
    knx.assert_state("light.test", STATE_ON, {ATTR_BRIGHTNESS: 255})
    await knx.receive_write(test_brightness, (128,))
    knx.assert_state("light.test", STATE_ON, {ATTR_BRIGHTNESS: 128})
    # turn off light via brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 0},
        blocking=True,
    )
    await knx.assert_write(test_address, False)
    knx.assert_state("light.test", STATE_OFF)


async def test_light_color_temp_absolute(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX light color temperature adjustable in Kelvin."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_ct = "1/1/5"
    test_ct_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM_NAME: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                    LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
                    LightSchema.CONF_COLOR_TEMP_ADDRESS: test_ct,
                    LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS: test_ct_state,
                    LightSchema.CONF_COLOR_TEMP_MODE: "absolute",
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_address_state)
    await knx.assert_read(test_brightness_state)
    await knx.receive_response(test_address_state, True)
    await knx.receive_response(test_brightness_state, (255,))
    # # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read(test_ct_state)
    await knx.receive_response(test_ct_state, (0x0A, 0x8C))  # 2700 Kelvin - 370 Mired

    knx.assert_state(
        "light.test",
        STATE_ON,
        {
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: COLOR_MODE_COLOR_TEMP,
            ATTR_COLOR_TEMP: 370,
        },
    )
    # change color temperature from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_TEMP: 250},  # 4000 Kelvin - 0x0FA0
        blocking=True,
    )
    await knx.assert_write(test_ct, (0x0F, 0xA0))
    knx.assert_state("light.test", STATE_ON, {ATTR_COLOR_TEMP: 250})
    # change color temperature from KNX
    await knx.receive_write(test_ct_state, (0x17, 0x70))  # 6000 Kelvin - 166 Mired
    knx.assert_state("light.test", STATE_ON, {ATTR_COLOR_TEMP: 166})


async def test_light_color_temp_relative(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX light color temperature adjustable in percent."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_ct = "1/1/5"
    test_ct_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM_NAME: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                    LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
                    LightSchema.CONF_COLOR_TEMP_ADDRESS: test_ct,
                    LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS: test_ct_state,
                    LightSchema.CONF_COLOR_TEMP_MODE: "relative",
                    LightSchema.CONF_MIN_KELVIN: 3000,
                    LightSchema.CONF_MAX_KELVIN: 4000,
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_address_state)
    await knx.assert_read(test_brightness_state)
    await knx.receive_response(test_address_state, True)
    await knx.receive_response(test_brightness_state, (255,))
    # # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read(test_ct_state)
    await knx.receive_response(test_ct_state, (0xFF,))  # 100 % - 4000 K - 250 Mired

    knx.assert_state(
        "light.test",
        STATE_ON,
        {
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_MODE: COLOR_MODE_COLOR_TEMP,
            ATTR_COLOR_TEMP: 250,
        },
    )
    # change color temperature from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_TEMP: 300},  # 3333 Kelvin - 33 % - 0x54
        blocking=True,
    )
    await knx.assert_write(test_ct, (0x54,))
    knx.assert_state("light.test", STATE_ON, {ATTR_COLOR_TEMP: 300})
    # change color temperature from KNX
    await knx.receive_write(test_ct_state, (0xE6,))  # 3900 Kelvin - 90 % - 256 Mired
    knx.assert_state("light.test", STATE_ON, {ATTR_COLOR_TEMP: 256})
