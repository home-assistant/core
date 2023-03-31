"""Test KNX light."""
from __future__ import annotations

from datetime import timedelta

from xknx.core import XknxConnectionState
from xknx.devices.light import Light as XknxLight

from homeassistant.components.knx.const import CONF_STATE_ADDRESS, KNX_ADDRESS
from homeassistant.components.knx.schema import LightSchema
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ColorMode,
)
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import KNXTestKit

from tests.common import async_fire_time_changed


async def test_light_simple(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test simple KNX light."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )

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
        color_mode=ColorMode.ONOFF,
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


async def test_light_brightness(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test dimmable KNX light."""
    test_address = "1/1/1"
    test_brightness = "1/1/2"
    test_brightness_state = "1/1/3"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
            }
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_brightness_state)
    await knx.xknx.connection_manager.connection_state_changed(
        XknxConnectionState.CONNECTED
    )
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
        brightness=80,
        color_mode=ColorMode.BRIGHTNESS,
    )
    # receive brightness changes from KNX
    await knx.receive_write(test_brightness_state, (255,))
    knx.assert_state("light.test", STATE_ON, brightness=255)
    await knx.receive_write(test_brightness, (128,))
    knx.assert_state("light.test", STATE_ON, brightness=128)
    # turn off light via brightness
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 0},
        blocking=True,
    )
    await knx.assert_write(test_address, False)
    knx.assert_state("light.test", STATE_OFF)


async def test_light_color_temp_absolute(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light color temperature adjustable in Kelvin."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_ct = "1/1/5"
    test_ct_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
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
        brightness=255,
        color_mode=ColorMode.COLOR_TEMP,
        color_temp=370,
        color_temp_kelvin=2700,
    )
    # change color temperature from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_TEMP_KELVIN: 4000},  # 4000 - 0x0FA0
        blocking=True,
    )
    await knx.assert_write(test_ct, (0x0F, 0xA0))
    knx.assert_state("light.test", STATE_ON, color_temp=250)
    # change color temperature from KNX
    await knx.receive_write(test_ct_state, (0x17, 0x70))  # 6000 Kelvin - 166 Mired
    knx.assert_state(
        "light.test",
        STATE_ON,
        color_temp=166,
        color_temp_kelvin=6000,
    )


async def test_light_color_temp_relative(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light color temperature adjustable in percent."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_ct = "1/1/5"
    test_ct_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
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
        brightness=255,
        color_mode=ColorMode.COLOR_TEMP,
        color_temp=250,
        color_temp_kelvin=4000,
    )
    # change color temperature from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.test",
            ATTR_COLOR_TEMP_KELVIN: 3333,  # 3333 Kelvin - 33.3 % - 0x55
        },
        blocking=True,
    )
    await knx.assert_write(test_ct, (0x55,))
    knx.assert_state(
        "light.test",
        STATE_ON,
        color_temp=300,
        color_temp_kelvin=3333,
    )
    # change color temperature from KNX
    await knx.receive_write(test_ct_state, (0xE6,))  # 3901 Kelvin - 90.1 % - 256 Mired
    knx.assert_state(
        "light.test",
        STATE_ON,
        color_temp=256,
        color_temp_kelvin=3901,
    )


async def test_light_hs_color(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with hs color."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_hue = "1/1/5"
    test_hue_state = "1/1/6"
    test_sat = "1/1/7"
    test_sat_state = "1/1/8"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                    LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
                    LightSchema.CONF_HUE_ADDRESS: test_hue,
                    LightSchema.CONF_HUE_STATE_ADDRESS: test_hue_state,
                    LightSchema.CONF_SATURATION_ADDRESS: test_sat,
                    LightSchema.CONF_SATURATION_STATE_ADDRESS: test_sat_state,
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
    await knx.assert_read(test_hue_state)
    await knx.assert_read(test_sat_state)
    await knx.receive_response(test_hue_state, (0xFF,))
    await knx.receive_response(test_sat_state, (0xFF,))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,
        color_mode=ColorMode.HS,
        hs_color=(360, 100),
    )
    # change color from HA - only hue
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "blue"},  # hue: 240, sat: 100
        blocking=True,
    )
    await knx.assert_write(test_hue, (0xAA,))
    knx.assert_state("light.test", STATE_ON, brightness=255, hs_color=(240, 100))

    # change color from HA - only saturation
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.test",
            ATTR_HS_COLOR: (240, 50),
        },  # hue: 60, sat: 12.157
        blocking=True,
    )
    await knx.assert_write(test_sat, (0x80,))
    knx.assert_state("light.test", STATE_ON, brightness=255, hs_color=(240, 50))

    # change color from HA - hue and sat
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "hotpink"},  # hue: 330, sat: 59
        blocking=True,
    )
    await knx.assert_write(test_hue, (0xEA,))
    await knx.assert_write(test_sat, (0x96,))
    knx.assert_state("light.test", STATE_ON, brightness=255, hs_color=(330, 59))

    # change color and brightness from KNX
    await knx.receive_write(test_brightness, (0xB2,))
    knx.assert_state("light.test", STATE_ON, brightness=178, hs_color=(330, 59))
    await knx.receive_write(test_hue, (0x7D,))
    knx.assert_state("light.test", STATE_ON, brightness=178, hs_color=(176, 59))
    await knx.receive_write(test_sat, (0xD1,))
    knx.assert_state("light.test", STATE_ON, brightness=178, hs_color=(176, 82))


async def test_light_xyy_color(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with xyy color."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_xyy = "1/1/5"
    test_xyy_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_XYY_ADDRESS: test_xyy,
                    LightSchema.CONF_XYY_STATE_ADDRESS: test_xyy_state,
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_address_state)
    await knx.assert_read(test_xyy_state)
    await knx.receive_response(test_address_state, True)
    await knx.receive_response(test_xyy_state, (0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0x03))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=204,
        color_mode=ColorMode.XY,
        xy_color=(0.8, 0.8),
    )
    # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 139, ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_xyy, (179, 116, 76, 139, 139, 3))
    knx.assert_state("light.test", STATE_ON, brightness=139, xy_color=(0.701, 0.299))

    # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await knx.assert_write(test_xyy, (0, 0, 0, 0, 255, 1))
    knx.assert_state("light.test", STATE_ON, brightness=255, xy_color=(0.701, 0.299))

    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_xyy, (120, 16, 63, 59, 0, 2))
    knx.assert_state("light.test", STATE_ON, brightness=255, xy_color=(0.469, 0.247))

    # change color and brightness from KNX
    await knx.receive_write(test_xyy, (0x85, 0x1E, 0x4F, 0x5C, 0x19, 0x03))
    knx.assert_state("light.test", STATE_ON, brightness=25, xy_color=(0.52, 0.31))
    # change brightness from KNX
    await knx.receive_write(test_xyy, (0x00, 0x00, 0x00, 0x00, 0x80, 0x01))
    knx.assert_state("light.test", STATE_ON, brightness=128, xy_color=(0.52, 0.31))
    # change color from KNX
    await knx.receive_write(test_xyy, (0x2E, 0x14, 0x40, 0x00, 0x00, 0x02))
    knx.assert_state("light.test", STATE_ON, brightness=128, xy_color=(0.18, 0.25))


async def test_light_xyy_color_with_brightness(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX light with xyy color and explicit brightness address."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_xyy = "1/1/5"
    test_xyy_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                    LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
                    LightSchema.CONF_XYY_ADDRESS: test_xyy,
                    LightSchema.CONF_XYY_STATE_ADDRESS: test_xyy_state,
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
    await knx.assert_read(test_xyy_state)
    await knx.receive_response(test_xyy_state, (0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0x03))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,  # brightness form xyy_color ignored when extra brightness GA is used
        color_mode=ColorMode.XY,
        xy_color=(0.8, 0.8),
    )
    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_xyy, (179, 116, 76, 139, 0, 2))
    knx.assert_state("light.test", STATE_ON, brightness=255, xy_color=(0.701, 0.299))

    # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 139},
        blocking=True,
    )
    await knx.assert_write(test_brightness, (0x8B,))
    knx.assert_state("light.test", STATE_ON, brightness=139, xy_color=(0.701, 0.299))

    # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 255, ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_xyy, (120, 16, 63, 59, 255, 3))
    # brightness relies on brightness_state GA
    await knx.receive_write(test_brightness_state, (255,))
    knx.assert_state("light.test", STATE_ON, brightness=255, xy_color=(0.469, 0.247))

    # change color and brightness from KNX
    await knx.receive_write(test_xyy, (0x85, 0x1E, 0x4F, 0x5C, 0x00, 0x02))
    knx.assert_state("light.test", STATE_ON, brightness=255, xy_color=(0.52, 0.31))
    await knx.receive_write(test_brightness, (21,))
    knx.assert_state("light.test", STATE_ON, brightness=21, xy_color=(0.52, 0.31))


async def test_light_rgb_individual(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with rgb color in individual GAs."""
    test_red = "1/1/3"
    test_red_state = "1/1/4"
    test_green = "1/1/5"
    test_green_state = "1/1/6"
    test_blue = "1/1/7"
    test_blue_state = "1/1/8"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    LightSchema.CONF_INDIVIDUAL_COLORS: {
                        LightSchema.CONF_RED: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_red,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_red_state,
                        },
                        LightSchema.CONF_GREEN: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_green,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_green_state,
                        },
                        LightSchema.CONF_BLUE: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_blue,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_blue_state,
                        },
                    },
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_red_state)
    await knx.assert_read(test_green_state)
    await knx.receive_response(test_red_state, (255,))
    await knx.receive_response(test_green_state, (255,))
    # # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read(test_blue_state)
    await knx.receive_response(test_blue_state, (255,))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,
        color_mode=ColorMode.RGB,
        rgb_color=(255, 255, 255),
    )
    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_red, (255,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=255, rgb_color=(255, 0, 0))

    # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 200},
        blocking=True,
    )
    await knx.assert_write(test_red, (200,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=200, rgb_color=(255, 0, 0))

    # change only color, keep brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_red, (200,))
    await knx.assert_write(test_green, (82,))
    await knx.assert_write(test_blue, (141,))
    knx.assert_state("light.test", STATE_ON, brightness=200, rgb_color=(255, 105, 180))

    # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 100, ATTR_COLOR_NAME: "yellow"},
        blocking=True,
    )
    await knx.assert_write(test_red, (100,))
    await knx.assert_write(test_green, (100,))
    await knx.assert_write(test_blue, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=100, rgb_color=(255, 255, 0))

    # turn OFF from KNX
    await knx.receive_write(test_red, (0,))
    await knx.receive_write(test_green, (0,))
    await knx.receive_write(test_blue, (0,))
    knx.assert_state("light.test", STATE_OFF)
    # turn ON from KNX
    await knx.receive_write(test_red, (0,))
    await knx.receive_write(test_green, (180,))
    await knx.receive_write(test_blue, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=180, rgb_color=(0, 255, 0))

    # turn OFF from HA
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test"},
        blocking=True,
    )
    await knx.assert_write(test_red, (0,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    knx.assert_state("light.test", STATE_OFF)

    # turn ON from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test"},
        blocking=True,
    )
    # color will not be restored - defaults to white
    await knx.assert_write(test_red, (255,))
    await knx.assert_write(test_green, (255,))
    await knx.assert_write(test_blue, (255,))
    knx.assert_state("light.test", STATE_ON, brightness=255, rgb_color=(255, 255, 255))

    # turn ON with brightness only from HA - defaults to white
    await knx.receive_write(test_red, (0,))
    await knx.receive_write(test_green, (0,))
    await knx.receive_write(test_blue, (0,))
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 45},
        blocking=True,
    )
    await knx.assert_write(test_red, (45,))
    await knx.assert_write(test_green, (45,))
    await knx.assert_write(test_blue, (45,))


async def test_light_rgbw_individual(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with rgbw color in individual GAs."""
    test_red = "1/1/3"
    test_red_state = "1/1/4"
    test_green = "1/1/5"
    test_green_state = "1/1/6"
    test_blue = "1/1/7"
    test_blue_state = "1/1/8"
    test_white = "1/1/9"
    test_white_state = "1/1/10"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    LightSchema.CONF_INDIVIDUAL_COLORS: {
                        LightSchema.CONF_RED: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_red,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_red_state,
                        },
                        LightSchema.CONF_GREEN: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_green,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_green_state,
                        },
                        LightSchema.CONF_BLUE: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_blue,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_blue_state,
                        },
                        LightSchema.CONF_WHITE: {
                            LightSchema.CONF_BRIGHTNESS_ADDRESS: test_white,
                            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_white_state,
                        },
                    },
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_red_state)
    await knx.assert_read(test_green_state)
    await knx.receive_response(test_red_state, (0,))
    await knx.receive_response(test_green_state, (0,))
    # # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read(test_blue_state)
    await knx.assert_read(test_white_state)
    await knx.receive_response(test_blue_state, (0,))
    await knx.receive_response(test_white_state, (255,))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,
        color_mode=ColorMode.RGBW,
        rgbw_color=(0, 0, 0, 255),
    )
    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_red, (255,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    await knx.assert_write(test_white, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=255, rgbw_color=(255, 0, 0, 0))

    # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 200},
        blocking=True,
    )
    await knx.assert_write(test_red, (200,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    await knx.assert_write(test_white, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=200, rgbw_color=(255, 0, 0, 0))

    # change only color, keep brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_red, (200,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (100,))
    await knx.assert_write(test_white, (139,))
    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=200,
        rgb_color=(255, 104, 179),  # minor rounding error - expected (255, 105, 180)
        rgbw_color=(255, 0, 127, 177),  # expected (255, 0, 128, 178)
    )

    # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 100, ATTR_COLOR_NAME: "yellow"},
        blocking=True,
    )
    await knx.assert_write(test_red, (100,))
    await knx.assert_write(test_green, (100,))
    await knx.assert_write(test_blue, (0,))
    await knx.assert_write(test_white, (0,))
    knx.assert_state(
        "light.test", STATE_ON, brightness=100, rgbw_color=(255, 255, 0, 0)
    )

    # turn OFF from KNX
    await knx.receive_write(test_red, (0,))
    await knx.receive_write(test_green, (0,))
    # # individual color debounce takes 0.2 seconds if not all 4 addresses received
    knx.assert_state("light.test", STATE_ON)
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=XknxLight.DEBOUNCE_TIMEOUT)
    )
    await knx.xknx.task_registry.block_till_done()
    knx.assert_state("light.test", STATE_OFF)
    # turn ON from KNX
    await knx.receive_write(test_red, (0,))
    await knx.receive_write(test_green, (180,))
    await knx.receive_write(test_blue, (0,))
    await knx.receive_write(test_white, (0,))
    knx.assert_state("light.test", STATE_ON, brightness=180, rgbw_color=(0, 255, 0, 0))

    # turn OFF from HA
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test"},
        blocking=True,
    )
    await knx.assert_write(test_red, (0,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    await knx.assert_write(test_white, (0,))
    knx.assert_state("light.test", STATE_OFF)

    # turn ON from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test"},
        blocking=True,
    )
    # color will not be restored - defaults to 100% on all channels
    await knx.assert_write(test_red, (255,))
    await knx.assert_write(test_green, (255,))
    await knx.assert_write(test_blue, (255,))
    await knx.assert_write(test_white, (255,))
    knx.assert_state(
        "light.test", STATE_ON, brightness=255, rgbw_color=(255, 255, 255, 255)
    )

    # turn ON with brightness only from HA - defaults to white
    await knx.receive_write(test_red, (0,))
    await knx.receive_write(test_green, (0,))
    await knx.receive_write(test_blue, (0,))
    await knx.receive_write(test_white, (0,))
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 45},
        blocking=True,
    )
    await knx.assert_write(test_red, (0,))
    await knx.assert_write(test_green, (0,))
    await knx.assert_write(test_blue, (0,))
    await knx.assert_write(test_white, (45,))


async def test_light_rgb(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with rgb color."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_rgb = "1/1/5"
    test_rgb_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_COLOR_ADDRESS: test_rgb,
                    LightSchema.CONF_COLOR_STATE_ADDRESS: test_rgb_state,
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_address_state)
    await knx.assert_read(test_rgb_state)
    await knx.receive_response(test_address_state, True)
    await knx.receive_response(test_rgb_state, (0xFF, 0xFF, 0xFF))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,
        color_mode=ColorMode.RGB,
        rgb_color=(255, 255, 255),
    )
    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_rgb, (255, 0, 0))
    knx.assert_state("light.test", STATE_ON, brightness=255, rgb_color=(255, 0, 0))

    # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 200},
        blocking=True,
    )
    await knx.assert_write(test_rgb, (200, 0, 0))
    knx.assert_state("light.test", STATE_ON, brightness=200, rgb_color=(255, 0, 0))

    # change color, keep brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_rgb, (200, 82, 141))
    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=200,
        rgb_color=(255, 105, 180),
    )
    # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 100, ATTR_COLOR_NAME: "yellow"},
        blocking=True,
    )
    await knx.assert_write(test_rgb, (100, 100, 0))
    knx.assert_state("light.test", STATE_ON, brightness=100, rgb_color=(255, 255, 0))

    # turn OFF from KNX
    await knx.receive_write(test_address_state, False)
    knx.assert_state("light.test", STATE_OFF)
    # receive color update from KNX - still OFF
    await knx.receive_write(test_rgb, (0, 180, 0))
    knx.assert_state("light.test", STATE_OFF)
    # turn ON from KNX - include color update
    await knx.receive_write(test_address_state, True)
    knx.assert_state("light.test", STATE_ON, brightness=180, rgb_color=(0, 255, 0))

    # turn OFF from HA
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test"},
        blocking=True,
    )
    await knx.assert_write(test_address, False)
    knx.assert_state("light.test", STATE_OFF)

    # turn ON from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test"},
        blocking=True,
    )
    # color will be restored in no other state was received
    await knx.assert_write(test_address, True)
    knx.assert_state("light.test", STATE_ON, brightness=180, rgb_color=(0, 255, 0))


async def test_light_rgbw(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with rgbw color."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_rgbw = "1/1/5"
    test_rgbw_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_RGBW_ADDRESS: test_rgbw,
                    LightSchema.CONF_RGBW_STATE_ADDRESS: test_rgbw_state,
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_address_state)
    await knx.assert_read(test_rgbw_state)
    await knx.receive_response(test_address_state, True)
    await knx.receive_response(test_rgbw_state, (0xFF, 0x65, 0x66, 0x67, 0x00, 0x0F))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,
        color_mode=ColorMode.RGBW,
        rgbw_color=(255, 101, 102, 103),
    )
    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (0xFF, 0x00, 0x00, 0x00, 0x00, 0x0F))
    knx.assert_state("light.test", STATE_ON, brightness=255, rgbw_color=(255, 0, 0, 0))

    # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 200},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (0xC8, 0x00, 0x00, 0x00, 0x00, 0x0F))
    knx.assert_state("light.test", STATE_ON, brightness=200, rgbw_color=(255, 0, 0, 0))

    # change color, keep brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (200, 0, 100, 139, 0x00, 0x0F))
    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=200,
        rgb_color=(255, 104, 179),  # minor rounding error - expected (255, 105, 180)
        rgbw_color=(255, 0, 127, 177),  # expected (255, 0, 128, 178)
    )
    # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 100, ATTR_COLOR_NAME: "yellow"},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (100, 100, 0, 0, 0x00, 0x0F))
    knx.assert_state(
        "light.test", STATE_ON, brightness=100, rgbw_color=(255, 255, 0, 0)
    )

    # turn OFF from KNX
    await knx.receive_write(test_address_state, False)
    knx.assert_state("light.test", STATE_OFF)
    # receive color update from KNX - still OFF
    await knx.receive_write(test_rgbw, (0, 180, 0, 0, 0x00, 0x0F))
    knx.assert_state("light.test", STATE_OFF)
    # turn ON from KNX - include color update
    await knx.receive_write(test_address_state, True)
    knx.assert_state("light.test", STATE_ON, brightness=180, rgbw_color=(0, 255, 0, 0))

    # turn OFF from HA
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.test"},
        blocking=True,
    )
    await knx.assert_write(test_address, False)
    knx.assert_state("light.test", STATE_OFF)

    # turn ON from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test"},
        blocking=True,
    )
    # color will be restored if no other state was received
    await knx.assert_write(test_address, True)
    knx.assert_state("light.test", STATE_ON, brightness=180, rgbw_color=(0, 255, 0, 0))


async def test_light_rgbw_brightness(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX light with rgbw color with dedicated brightness."""
    test_address = "1/1/1"
    test_address_state = "1/1/2"
    test_brightness = "1/1/3"
    test_brightness_state = "1/1/4"
    test_rgbw = "1/1/5"
    test_rgbw_state = "1/1/6"
    await knx.setup_integration(
        {
            LightSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    KNX_ADDRESS: test_address,
                    CONF_STATE_ADDRESS: test_address_state,
                    LightSchema.CONF_BRIGHTNESS_ADDRESS: test_brightness,
                    LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS: test_brightness_state,
                    LightSchema.CONF_RGBW_ADDRESS: test_rgbw,
                    LightSchema.CONF_RGBW_STATE_ADDRESS: test_rgbw_state,
                },
            ]
        }
    )
    # StateUpdater initialize state
    await knx.assert_read(test_address_state)
    await knx.assert_read(test_brightness_state)
    await knx.receive_response(test_address_state, True)
    await knx.receive_response(test_brightness_state, (0xFF,))
    await knx.assert_read(test_rgbw_state)
    await knx.receive_response(test_rgbw_state, (0xFF, 0x65, 0x66, 0x67, 0x00, 0x0F))

    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=255,
        color_mode=ColorMode.RGBW,
        rgbw_color=(255, 101, 102, 103),
    )
    # change color from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_COLOR_NAME: "red"},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (0xFF, 0x00, 0x00, 0x00, 0x00, 0x0F))
    knx.assert_state("light.test", STATE_ON, brightness=255, rgbw_color=(255, 0, 0, 0))
    # # update from dedicated brightness state
    await knx.receive_write(test_brightness_state, (0xF0,))
    knx.assert_state("light.test", STATE_ON, brightness=240, rgbw_color=(255, 0, 0, 0))

    # single encoded brightness - at least one primary color = 255
    # # change brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    await knx.assert_write(test_brightness, (128,))
    knx.assert_state("light.test", STATE_ON, brightness=128, rgbw_color=(255, 0, 0, 0))
    # # change color and brightness from HA
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_BRIGHTNESS: 128, ATTR_COLOR_NAME: "hotpink"},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (255, 0, 128, 178, 0x00, 0x0F))
    await knx.assert_write(test_brightness, (128,))
    knx.assert_state(
        "light.test",
        STATE_ON,
        brightness=128,
        rgb_color=(255, 105, 180),
        rgbw_color=(255, 0, 128, 178),
    )

    # doubly encoded brightness
    # brightness is handled by dedicated brightness address only
    # # from dedicated rgbw state
    await knx.receive_write(test_rgbw_state, (0xC8, 0x00, 0x00, 0x00, 0x00, 0x0F))
    knx.assert_state("light.test", STATE_ON, brightness=128, rgbw_color=(200, 0, 0, 0))
    # # from HA - only color
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", ATTR_RGBW_COLOR: (20, 30, 40, 50)},
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (20, 30, 40, 50, 0x00, 0x0F))
    knx.assert_state(
        "light.test", STATE_ON, brightness=128, rgbw_color=(20, 30, 40, 50)
    )
    # # from HA - brightness and color
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.test",
            ATTR_BRIGHTNESS: 50,
            ATTR_RGBW_COLOR: (100, 200, 55, 12),
        },
        blocking=True,
    )
    await knx.assert_write(test_rgbw, (100, 200, 55, 12, 0x00, 0x0F))
    await knx.assert_write(test_brightness, (50,))
    knx.assert_state(
        "light.test", STATE_ON, brightness=50, rgbw_color=(100, 200, 55, 12)
    )
