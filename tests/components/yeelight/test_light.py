"""Test the Yeelight light."""
import asyncio
from datetime import timedelta
import logging
import socket
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
from yeelight import (
    BulbException,
    BulbType,
    HSVTransition,
    LightType,
    PowerMode,
    RGBTransition,
    SceneClass,
    SleepTransition,
    TemperatureTransition,
    transitions,
)
from yeelight.flow import Action, Flow
from yeelight.main import _MODEL_SPECS

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    FLASH_LONG,
    FLASH_SHORT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    LightEntityFeature,
)
from homeassistant.components.yeelight.const import (
    ATTR_COUNT,
    ATTR_MODE_MUSIC,
    ATTR_TRANSITIONS,
    CONF_CUSTOM_EFFECTS,
    CONF_FLOW_PARAMS,
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DEFAULT_MODE_MUSIC,
    DEFAULT_NIGHTLIGHT_SWITCH,
    DEFAULT_SAVE_ON_CHANGE,
    DEFAULT_TRANSITION,
    DOMAIN,
    YEELIGHT_HSV_TRANSACTION,
    YEELIGHT_RGB_TRANSITION,
    YEELIGHT_SLEEP_TRANSACTION,
    YEELIGHT_TEMPERATURE_TRANSACTION,
)
from homeassistant.components.yeelight.light import (
    ATTR_MINUTES,
    ATTR_MODE,
    EFFECT_CANDLE_FLICKER,
    EFFECT_DATE_NIGHT,
    EFFECT_DISCO,
    EFFECT_FACEBOOK,
    EFFECT_FAST_RANDOM_LOOP,
    EFFECT_HAPPY_BIRTHDAY,
    EFFECT_HOME,
    EFFECT_MOVIE,
    EFFECT_NIGHT_MODE,
    EFFECT_ROMANCE,
    EFFECT_STOP,
    EFFECT_SUNRISE,
    EFFECT_SUNSET,
    EFFECT_TWITTER,
    EFFECT_WHATSAPP,
    SERVICE_SET_AUTO_DELAY_OFF_SCENE,
    SERVICE_SET_COLOR_FLOW_SCENE,
    SERVICE_SET_COLOR_SCENE,
    SERVICE_SET_COLOR_TEMP_SCENE,
    SERVICE_SET_HSV_SCENE,
    SERVICE_SET_MODE,
    SERVICE_SET_MUSIC_MODE,
    SERVICE_START_FLOW,
    YEELIGHT_COLOR_EFFECT_LIST,
    YEELIGHT_MONO_EFFECT_LIST,
    YEELIGHT_TEMP_ONLY_EFFECT_LIST,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_hs_to_xy,
    color_RGB_to_hs,
    color_RGB_to_xy,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import (
    CAPABILITIES,
    ENTITY_LIGHT,
    ENTITY_NIGHTLIGHT,
    IP_ADDRESS,
    MODULE,
    NAME,
    PROPERTIES,
    UNIQUE_FRIENDLY_NAME,
    _mocked_bulb,
    _patch_discovery,
    _patch_discovery_interval,
)

from tests.common import MockConfigEntry, async_fire_time_changed

CONFIG_ENTRY_DATA = {
    CONF_HOST: IP_ADDRESS,
    CONF_TRANSITION: DEFAULT_TRANSITION,
    CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
    CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
    CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
}

SUPPORT_YEELIGHT = (
    LightEntityFeature.TRANSITION | LightEntityFeature.FLASH | LightEntityFeature.EFFECT
)


async def test_services(hass: HomeAssistant, caplog):
    """Test Yeelight services."""
    assert await async_setup_component(hass, "homeassistant", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **CONFIG_ENTRY_DATA,
            CONF_MODE_MUSIC: True,
            CONF_SAVE_ON_CHANGE: True,
            CONF_NIGHTLIGHT_SWITCH: True,
        },
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.AsyncBulb", return_value=mocked_bulb
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON
    assert hass.states.get(ENTITY_NIGHTLIGHT).state == STATE_OFF

    async def _async_test_service(
        service,
        data,
        method,
        payload=None,
        domain=DOMAIN,
        failure_side_effect=HomeAssistantError,
    ):
        err_count = len([x for x in caplog.records if x.levelno == logging.ERROR])

        # success
        if method.startswith("async_"):
            mocked_method = AsyncMock()
        else:
            mocked_method = MagicMock()
        setattr(mocked_bulb, method, mocked_method)
        await hass.services.async_call(domain, service, data, blocking=True)
        if payload is None:
            mocked_method.assert_called_once()
        elif type(payload) == list:
            mocked_method.assert_called_once_with(*payload)
        else:
            mocked_method.assert_called_once_with(**payload)
        assert (
            len([x for x in caplog.records if x.levelno == logging.ERROR]) == err_count
        )

        # failure
        if failure_side_effect:
            if method.startswith("async_"):
                mocked_method = AsyncMock(side_effect=failure_side_effect)
            else:
                mocked_method = MagicMock(side_effect=failure_side_effect)
            setattr(mocked_bulb, method, mocked_method)
            with pytest.raises(failure_side_effect):
                await hass.services.async_call(domain, service, data, blocking=True)

    # turn_on rgb_color
    brightness = 100
    rgb_color = (0, 128, 255)
    transition = 2
    mocked_bulb.last_properties["power"] = "off"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS: brightness,
            ATTR_RGB_COLOR: rgb_color,
            ATTR_FLASH: FLASH_LONG,
            ATTR_EFFECT: EFFECT_STOP,
            ATTR_TRANSITION: transition,
        },
        blocking=True,
    )
    mocked_bulb.async_turn_on.assert_called_once_with(
        duration=transition * 1000,
        light_type=LightType.Main,
        power_mode=PowerMode.NORMAL,
    )
    mocked_bulb.async_turn_on.reset_mock()
    mocked_bulb.async_start_music.assert_called_once()
    mocked_bulb.async_start_music.reset_mock()
    mocked_bulb.async_set_brightness.assert_called_once_with(
        brightness / 255 * 100, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.async_set_brightness.reset_mock()
    mocked_bulb.async_set_color_temp.assert_not_called()
    mocked_bulb.async_set_color_temp.reset_mock()
    mocked_bulb.async_set_hsv.assert_not_called()
    mocked_bulb.async_set_hsv.reset_mock()
    mocked_bulb.async_set_rgb.assert_called_once_with(
        *rgb_color, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.async_set_rgb.reset_mock()
    mocked_bulb.async_start_flow.assert_called_once()  # flash
    mocked_bulb.async_start_flow.reset_mock()
    mocked_bulb.async_stop_flow.assert_called_once_with(light_type=LightType.Main)
    mocked_bulb.async_stop_flow.reset_mock()

    # turn_on hs_color
    brightness = 100
    hs_color = (180, 100)
    transition = 2
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS: brightness,
            ATTR_HS_COLOR: hs_color,
            ATTR_FLASH: FLASH_LONG,
            ATTR_EFFECT: EFFECT_STOP,
            ATTR_TRANSITION: transition,
        },
        blocking=True,
    )
    mocked_bulb.async_turn_on.assert_called_once_with(
        duration=transition * 1000,
        light_type=LightType.Main,
        power_mode=PowerMode.NORMAL,
    )
    mocked_bulb.async_turn_on.reset_mock()
    mocked_bulb.async_start_music.assert_called_once()
    mocked_bulb.async_start_music.reset_mock()
    mocked_bulb.async_set_brightness.assert_called_once_with(
        brightness / 255 * 100, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.async_set_brightness.reset_mock()
    mocked_bulb.async_set_color_temp.assert_not_called()
    mocked_bulb.async_set_color_temp.reset_mock()
    mocked_bulb.async_set_hsv.assert_called_once_with(
        *hs_color, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.async_set_hsv.reset_mock()
    mocked_bulb.async_set_rgb.assert_not_called()
    mocked_bulb.async_set_rgb.reset_mock()
    mocked_bulb.async_start_flow.assert_called_once()  # flash
    mocked_bulb.async_start_flow.reset_mock()
    mocked_bulb.async_stop_flow.assert_called_once_with(light_type=LightType.Main)
    mocked_bulb.async_stop_flow.reset_mock()

    # turn_on color_temp
    brightness = 100
    color_temp = 200
    transition = 1
    mocked_bulb.last_properties["power"] = "off"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS: brightness,
            ATTR_COLOR_TEMP: color_temp,
            ATTR_FLASH: FLASH_LONG,
            ATTR_EFFECT: EFFECT_STOP,
            ATTR_TRANSITION: transition,
        },
        blocking=True,
    )
    mocked_bulb.async_turn_on.assert_called_once_with(
        duration=transition * 1000,
        light_type=LightType.Main,
        power_mode=PowerMode.NORMAL,
    )
    mocked_bulb.async_turn_on.reset_mock()
    mocked_bulb.async_start_music.assert_called_once()
    mocked_bulb.async_set_brightness.assert_called_once_with(
        brightness / 255 * 100, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.async_set_color_temp.assert_called_once_with(
        color_temperature_mired_to_kelvin(color_temp),
        duration=transition * 1000,
        light_type=LightType.Main,
    )
    mocked_bulb.async_set_hsv.assert_not_called()
    mocked_bulb.async_set_rgb.assert_not_called()
    mocked_bulb.async_start_flow.assert_called_once()  # flash
    mocked_bulb.async_stop_flow.assert_called_once_with(light_type=LightType.Main)

    # turn_on color_temp - flash short
    brightness = 100
    color_temp = 200
    transition = 1
    mocked_bulb.async_start_music.reset_mock()
    mocked_bulb.async_set_brightness.reset_mock()
    mocked_bulb.async_set_color_temp.reset_mock()
    mocked_bulb.async_start_flow.reset_mock()
    mocked_bulb.async_stop_flow.reset_mock()

    mocked_bulb.last_properties["power"] = "off"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS: brightness,
            ATTR_COLOR_TEMP: color_temp,
            ATTR_FLASH: FLASH_SHORT,
            ATTR_EFFECT: EFFECT_STOP,
            ATTR_TRANSITION: transition,
        },
        blocking=True,
    )
    mocked_bulb.async_turn_on.assert_called_once_with(
        duration=transition * 1000,
        light_type=LightType.Main,
        power_mode=PowerMode.NORMAL,
    )
    mocked_bulb.async_turn_on.reset_mock()
    mocked_bulb.async_start_music.assert_called_once()
    mocked_bulb.async_set_brightness.assert_called_once_with(
        brightness / 255 * 100, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.async_set_color_temp.assert_called_once_with(
        color_temperature_mired_to_kelvin(color_temp),
        duration=transition * 1000,
        light_type=LightType.Main,
    )
    mocked_bulb.async_set_hsv.assert_not_called()
    mocked_bulb.async_set_rgb.assert_not_called()
    mocked_bulb.async_start_flow.assert_called_once()  # flash
    mocked_bulb.async_stop_flow.assert_called_once_with(light_type=LightType.Main)

    # turn_on nightlight
    await _async_test_service(
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_NIGHTLIGHT},
        "async_turn_on",
        payload={
            "duration": DEFAULT_TRANSITION,
            "light_type": LightType.Main,
            "power_mode": PowerMode.MOONLIGHT,
        },
        domain="light",
    )

    mocked_bulb.last_properties["power"] = "on"
    assert hass.states.get(ENTITY_LIGHT).state != STATE_UNAVAILABLE
    # turn_off
    await _async_test_service(
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_TRANSITION: transition},
        "async_turn_off",
        domain="light",
        payload={"duration": transition * 1000, "light_type": LightType.Main},
    )

    # set_mode
    mode = "rgb"
    await _async_test_service(
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE: "rgb"},
        "async_set_power_mode",
        [PowerMode[mode.upper()]],
    )

    # start_flow
    await _async_test_service(
        SERVICE_START_FLOW,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_TRANSITIONS: [{YEELIGHT_TEMPERATURE_TRANSACTION: [1900, 2000, 60]}],
        },
        "async_start_flow",
    )

    # set_color_scene
    await _async_test_service(
        SERVICE_SET_COLOR_SCENE,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_RGB_COLOR: [10, 20, 30],
            ATTR_BRIGHTNESS: 50,
        },
        "async_set_scene",
        [SceneClass.COLOR, 10, 20, 30, 50],
    )

    # set_hsv_scene
    await _async_test_service(
        SERVICE_SET_HSV_SCENE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_HS_COLOR: [180, 50], ATTR_BRIGHTNESS: 50},
        "async_set_scene",
        [SceneClass.HSV, 180, 50, 50],
    )

    # set_color_temp_scene
    await _async_test_service(
        SERVICE_SET_COLOR_TEMP_SCENE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_KELVIN: 4000, ATTR_BRIGHTNESS: 50},
        "async_set_scene",
        [SceneClass.CT, 4000, 50],
    )

    # set_color_flow_scene
    await _async_test_service(
        SERVICE_SET_COLOR_FLOW_SCENE,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_TRANSITIONS: [{YEELIGHT_TEMPERATURE_TRANSACTION: [1900, 2000, 60]}],
        },
        "async_set_scene",
    )

    # set_auto_delay_off_scene
    await _async_test_service(
        SERVICE_SET_AUTO_DELAY_OFF_SCENE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MINUTES: 1, ATTR_BRIGHTNESS: 50},
        "async_set_scene",
        [SceneClass.AUTO_DELAY_OFF, 50, 1],
    )

    # set_music_mode failure enable
    mocked_bulb.async_start_music = MagicMock(side_effect=AssertionError)
    assert "Unable to turn on music mode, consider disabling it" not in caplog.text
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MUSIC_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE_MUSIC: "true"},
        blocking=True,
    )
    assert mocked_bulb.async_start_music.mock_calls == [call()]
    assert "Unable to turn on music mode, consider disabling it" in caplog.text

    # set_music_mode disable
    await _async_test_service(
        SERVICE_SET_MUSIC_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE_MUSIC: "false"},
        "async_stop_music",
        failure_side_effect=None,
    )

    # set_music_mode success enable
    await _async_test_service(
        SERVICE_SET_MUSIC_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE_MUSIC: "true"},
        "async_start_music",
        failure_side_effect=None,
    )
    # test _cmd wrapper error handler
    mocked_bulb.last_properties["power"] = "off"
    mocked_bulb.available = True
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    assert hass.states.get(ENTITY_LIGHT).state == STATE_OFF

    mocked_bulb.async_turn_on = AsyncMock()
    mocked_bulb.async_set_brightness = AsyncMock(side_effect=BulbException)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 50},
            blocking=True,
        )
    assert hass.states.get(ENTITY_LIGHT).state == STATE_OFF

    mocked_bulb.async_set_brightness = AsyncMock(side_effect=asyncio.TimeoutError)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 55},
            blocking=True,
        )
    assert hass.states.get(ENTITY_LIGHT).state == STATE_OFF

    mocked_bulb.async_set_brightness = AsyncMock(side_effect=socket.error)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 55},
            blocking=True,
        )
    assert hass.states.get(ENTITY_LIGHT).state == STATE_UNAVAILABLE


async def test_update_errors(hass: HomeAssistant, caplog):
    """Test update errors."""
    assert await async_setup_component(hass, "homeassistant", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **CONFIG_ENTRY_DATA,
            CONF_MODE_MUSIC: True,
            CONF_SAVE_ON_CHANGE: True,
            CONF_NIGHTLIGHT_SWITCH: True,
        },
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.AsyncBulb", return_value=mocked_bulb
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON
    assert hass.states.get(ENTITY_NIGHTLIGHT).state == STATE_OFF

    # Timeout usually means the bulb is overloaded with commands
    # but will still respond eventually.
    mocked_bulb.async_turn_off = AsyncMock(side_effect=asyncio.TimeoutError)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )
    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    # socket.error usually means the bulb dropped the connection
    # or lost wifi, then came back online and forced the existing
    # connection closed with a TCP RST
    mocked_bulb.async_turn_off = AsyncMock(side_effect=socket.error)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_LIGHT},
            blocking=True,
        )
    assert hass.states.get(ENTITY_LIGHT).state == STATE_UNAVAILABLE


async def test_state_already_set_avoid_ratelimit(hass: HomeAssistant):
    """Ensure we suppress state changes that will increase the rate limit when there is no change."""
    mocked_bulb = _mocked_bulb()
    properties = {**PROPERTIES}
    properties.pop("active_mode")
    properties.pop("nl_br")
    properties["color_mode"] = "3"  # HSV
    mocked_bulb.last_properties = properties
    mocked_bulb.bulb_type = BulbType.Color
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: False}
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.AsyncBulb", return_value=mocked_bulb
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        # We use asyncio.create_task now to avoid
        # blocking starting so we need to block again
        await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_HS_COLOR: (PROPERTIES["hue"], PROPERTIES["sat"]),
        },
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []

    mocked_bulb.last_properties["color_mode"] = 1
    rgb = int(PROPERTIES["rgb"])
    blue = rgb & 0xFF
    green = (rgb >> 8) & 0xFF
    red = (rgb >> 16) & 0xFF

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGB_COLOR: (red, green, blue)},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []
    mocked_bulb.async_set_rgb.reset_mock()

    mocked_bulb.last_properties["flowing"] = "1"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGB_COLOR: (red, green, blue)},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == [
        call(255, 0, 0, duration=350, light_type=ANY)
    ]
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []
    mocked_bulb.async_set_rgb.reset_mock()
    mocked_bulb.last_properties["flowing"] = "0"

    mocked_bulb.model = "color"  # color model needs a workaround (see MODELS_WITH_DELAYED_ON_TRANSITION)
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS_PCT: PROPERTIES["bright"],
        },
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == [
        call(pytest.approx(50.1, 0.1), duration=350, light_type=ANY)
    ]
    mocked_bulb.async_set_brightness.reset_mock()

    mocked_bulb.model = "colora"  # colora does not need a workaround
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS_PCT: PROPERTIES["bright"],
        },
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP: 250},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    # Should call for the color mode change
    assert mocked_bulb.async_set_color_temp.mock_calls == [
        call(4000, duration=350, light_type=ANY)
    ]
    assert mocked_bulb.async_set_brightness.mock_calls == []
    mocked_bulb.async_set_color_temp.reset_mock()

    mocked_bulb.last_properties["color_mode"] = 2
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP: 250},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []

    mocked_bulb.last_properties["flowing"] = "1"

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP: 250},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == [
        call(4000, duration=350, light_type=ANY)
    ]
    assert mocked_bulb.async_set_brightness.mock_calls == []
    mocked_bulb.async_set_color_temp.reset_mock()
    mocked_bulb.last_properties["flowing"] = "0"

    mocked_bulb.last_properties["color_mode"] = 3
    # This last change should generate a call even though
    # the color mode is the same since the HSV has changed
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_HS_COLOR: (5, 5)},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == [
        call(5.0, 5.0, duration=350, light_type=ANY)
    ]
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []
    mocked_bulb.async_set_hsv.reset_mock()

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_HS_COLOR: (100, 35)},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == []
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []

    mocked_bulb.last_properties["flowing"] = "1"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_HS_COLOR: (100, 35)},
        blocking=True,
    )
    assert mocked_bulb.async_set_hsv.mock_calls == [
        call(100.0, 35.0, duration=350, light_type=ANY)
    ]
    assert mocked_bulb.async_set_rgb.mock_calls == []
    assert mocked_bulb.async_set_color_temp.mock_calls == []
    assert mocked_bulb.async_set_brightness.mock_calls == []
    mocked_bulb.last_properties["flowing"] = "0"


async def test_device_types(hass: HomeAssistant, caplog):
    """Test different device types."""
    mocked_bulb = _mocked_bulb()
    properties = {**PROPERTIES}
    properties.pop("active_mode")
    properties["color_mode"] = "3"  # HSV
    mocked_bulb.last_properties = properties

    async def _async_setup(config_entry):
        with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb):
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            # We use asyncio.create_task now to avoid
            # blocking starting so we need to block again
            await hass.async_block_till_done()

    async def _async_test(
        bulb_type,
        model,
        target_properties,
        nightlight_entity_properties=None,
        name=UNIQUE_FRIENDLY_NAME,
        entity_id=ENTITY_LIGHT,
        nightlight_mode_properties=None,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: False}
        )
        config_entry.add_to_hass(hass)

        mocked_bulb.bulb_type = bulb_type
        model_specs = _MODEL_SPECS.get(model)
        type(mocked_bulb).get_model_specs = MagicMock(return_value=model_specs)
        original_nightlight_brightness = mocked_bulb.last_properties["nl_br"]

        mocked_bulb.last_properties["nl_br"] = "0"
        await _async_setup(config_entry)

        state = hass.states.get(entity_id)

        assert state.state == "on"
        target_properties["friendly_name"] = name
        target_properties["flowing"] = False
        target_properties["night_light"] = False
        target_properties["music_mode"] = False
        assert dict(state.attributes) == target_properties
        await hass.config_entries.async_unload(config_entry.entry_id)
        await config_entry.async_remove(hass)
        registry = er.async_get(hass)
        registry.async_clear_config_entry(config_entry.entry_id)
        mocked_bulb.last_properties["nl_br"] = original_nightlight_brightness

        # nightlight as a setting of the main entity
        if nightlight_mode_properties is not None:
            mocked_bulb.last_properties["active_mode"] = True
            config_entry.add_to_hass(hass)
            await _async_setup(config_entry)
            state = hass.states.get(entity_id)
            assert state.state == "on"
            nightlight_mode_properties["friendly_name"] = name
            nightlight_mode_properties["flowing"] = False
            nightlight_mode_properties["night_light"] = True
            nightlight_mode_properties["music_mode"] = False
            assert dict(state.attributes) == nightlight_mode_properties

            await hass.config_entries.async_unload(config_entry.entry_id)
            await config_entry.async_remove(hass)
            registry.async_clear_config_entry(config_entry.entry_id)
            await hass.async_block_till_done()
            mocked_bulb.last_properties.pop("active_mode")

        # nightlight as a separate entity
        if nightlight_entity_properties is not None:
            config_entry = MockConfigEntry(
                domain=DOMAIN, data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: True}
            )
            config_entry.add_to_hass(hass)
            await _async_setup(config_entry)

            assert hass.states.get(entity_id).state == "off"
            state = hass.states.get(f"{entity_id}_nightlight")
            assert state.state == "on"
            nightlight_entity_properties["friendly_name"] = f"{name} Nightlight"
            nightlight_entity_properties["icon"] = "mdi:weather-night"
            nightlight_entity_properties["flowing"] = False
            nightlight_entity_properties["night_light"] = True
            nightlight_entity_properties["music_mode"] = False
            assert dict(state.attributes) == nightlight_entity_properties

            await hass.config_entries.async_unload(config_entry.entry_id)
            await config_entry.async_remove(hass)
            registry.async_clear_config_entry(config_entry.entry_id)
            await hass.async_block_till_done()

    bright = round(255 * int(PROPERTIES["bright"]) / 100)
    ct = color_temperature_kelvin_to_mired(int(PROPERTIES["ct"]))
    hue = int(PROPERTIES["hue"])
    sat = int(PROPERTIES["sat"])
    rgb = int(PROPERTIES["rgb"])
    rgb_color = ((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF)
    hs_color = (hue, sat)
    bg_bright = round(255 * int(PROPERTIES["bg_bright"]) / 100)
    bg_ct = color_temperature_kelvin_to_mired(int(PROPERTIES["bg_ct"]))
    bg_hue = int(PROPERTIES["bg_hue"])
    bg_sat = int(PROPERTIES["bg_sat"])
    bg_rgb = int(PROPERTIES["bg_rgb"])
    bg_hs_color = (bg_hue, bg_sat)
    bg_rgb_color = ((bg_rgb >> 16) & 0xFF, (bg_rgb >> 8) & 0xFF, bg_rgb & 0xFF)
    nl_br = round(255 * int(PROPERTIES["nl_br"]) / 100)

    # Default
    await _async_test(
        None,
        "mono",
        {
            "effect_list": YEELIGHT_MONO_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "brightness": bright,
            "color_mode": "brightness",
            "supported_color_modes": ["brightness"],
        },
    )

    # White
    await _async_test(
        BulbType.White,
        "mono",
        {
            "effect_list": YEELIGHT_MONO_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "brightness": bright,
            "color_mode": "brightness",
            "supported_color_modes": ["brightness"],
        },
    )

    # Color - color mode CT
    mocked_bulb.last_properties["color_mode"] = "2"  # CT
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "color_temp": ct,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
            "hs_color": (26.812, 34.87),
            "rgb_color": (255, 205, 166),
            "xy_color": (0.421, 0.364),
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
        nightlight_mode_properties={
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "hs_color": (28.401, 100.0),
            "rgb_color": (255, 120, 0),
            "xy_color": (0.621, 0.367),
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": nl_br,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
            "color_temp": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
        },
    )

    # Color - color mode HS
    mocked_bulb.last_properties["color_mode"] = "3"  # HSV
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "hs_color": hs_color,
            "rgb_color": color_hs_to_RGB(*hs_color),
            "xy_color": color_hs_to_xy(*hs_color),
            "color_mode": "hs",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
    )

    # Color - color mode RGB
    mocked_bulb.last_properties["color_mode"] = "1"  # RGB
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "hs_color": color_RGB_to_hs(*rgb_color),
            "rgb_color": rgb_color,
            "xy_color": color_RGB_to_xy(*rgb_color),
            "color_mode": "rgb",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
    )

    # Color - color mode HS but no hue
    mocked_bulb.last_properties["color_mode"] = "3"  # HSV
    mocked_bulb.last_properties["hue"] = None
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "color_mode": "hs",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
    )

    # Color - color mode RGB but no color
    mocked_bulb.last_properties["color_mode"] = "1"  # RGB
    mocked_bulb.last_properties["rgb"] = None
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "color_mode": "rgb",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
    )

    # Color - unsupported color_mode
    mocked_bulb.last_properties["color_mode"] = 4  # Unsupported
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "color_mode": "unknown",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        {
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
    )
    assert "Light reported unknown color mode: 4" in caplog.text

    # WhiteTemp
    model_specs = _MODEL_SPECS["ceiling1"]
    await _async_test(
        BulbType.WhiteTemp,
        "ceiling1",
        {
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "color_temp": ct,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp"],
            "hs_color": (26.812, 34.87),
            "rgb_color": (255, 205, 166),
            "xy_color": (0.421, 0.364),
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "brightness": nl_br,
            "color_mode": "brightness",
            "supported_color_modes": ["brightness"],
        },
        nightlight_mode_properties={
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": nl_br,
            "color_temp": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp"],
            "hs_color": (28.391, 65.659),
            "rgb_color": (255, 166, 87),
            "xy_color": (0.526, 0.387),
        },
    )

    # WhiteTempMood
    properties.pop("power")
    properties["main_power"] = "on"
    model_specs = _MODEL_SPECS["ceiling4"]
    await _async_test(
        BulbType.WhiteTempMood,
        "ceiling4",
        {
            "friendly_name": NAME,
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "flowing": False,
            "night_light": True,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": bright,
            "color_temp": ct,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp"],
            "hs_color": (26.812, 34.87),
            "rgb_color": (255, 205, 166),
            "xy_color": (0.421, 0.364),
        },
        nightlight_entity_properties={
            "supported_features": 0,
            "brightness": nl_br,
            "color_mode": "brightness",
            "supported_color_modes": ["brightness"],
        },
        nightlight_mode_properties={
            "friendly_name": NAME,
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "flowing": False,
            "night_light": True,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": nl_br,
            "color_temp": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp"],
            "hs_color": (28.391, 65.659),
            "rgb_color": (255, 166, 87),
            "xy_color": (0.526, 0.387),
        },
    )
    # Background light - color mode CT
    mocked_bulb.last_properties["bg_lmode"] = "2"  # CT
    await _async_test(
        BulbType.WhiteTempMood,
        "ceiling4",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(6500),
            "max_mireds": color_temperature_kelvin_to_mired(1700),
            "brightness": bg_bright,
            "color_temp": bg_ct,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
            "hs_color": (27.001, 19.243),
            "rgb_color": (255, 228, 205),
            "xy_color": (0.372, 0.35),
        },
        name=f"{UNIQUE_FRIENDLY_NAME} Ambilight",
        entity_id=f"{ENTITY_LIGHT}_ambilight",
    )

    # Background light - color mode HS
    mocked_bulb.last_properties["bg_lmode"] = "3"  # HS
    await _async_test(
        BulbType.WhiteTempMood,
        "ceiling4",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(6500),
            "max_mireds": color_temperature_kelvin_to_mired(1700),
            "brightness": bg_bright,
            "hs_color": bg_hs_color,
            "rgb_color": color_hs_to_RGB(*bg_hs_color),
            "xy_color": color_hs_to_xy(*bg_hs_color),
            "color_mode": "hs",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        name=f"{UNIQUE_FRIENDLY_NAME} Ambilight",
        entity_id=f"{ENTITY_LIGHT}_ambilight",
    )

    # Background light - color mode RGB
    mocked_bulb.last_properties["bg_lmode"] = "1"  # RGB
    await _async_test(
        BulbType.WhiteTempMood,
        "ceiling4",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "min_mireds": color_temperature_kelvin_to_mired(6500),
            "max_mireds": color_temperature_kelvin_to_mired(1700),
            "brightness": bg_bright,
            "hs_color": color_RGB_to_hs(*bg_rgb_color),
            "rgb_color": bg_rgb_color,
            "xy_color": color_RGB_to_xy(*bg_rgb_color),
            "color_mode": "rgb",
            "supported_color_modes": ["color_temp", "hs", "rgb"],
        },
        name=f"{UNIQUE_FRIENDLY_NAME} Ambilight",
        entity_id=f"{ENTITY_LIGHT}_ambilight",
    )


async def test_effects(hass: HomeAssistant):
    """Test effects."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_CUSTOM_EFFECTS: [
                    {
                        CONF_NAME: "mock_effect",
                        CONF_FLOW_PARAMS: {
                            ATTR_COUNT: 3,
                            ATTR_TRANSITIONS: [
                                {YEELIGHT_HSV_TRANSACTION: [300, 50, 500, 50]},
                                {YEELIGHT_RGB_TRANSITION: [100, 100, 100, 300, 30]},
                                {YEELIGHT_TEMPERATURE_TRANSACTION: [3000, 200, 20]},
                                {YEELIGHT_SLEEP_TRANSACTION: [800]},
                            ],
                        },
                    }
                ]
            }
        },
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.AsyncBulb", return_value=mocked_bulb
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).attributes.get(
        "effect_list"
    ) == YEELIGHT_COLOR_EFFECT_LIST + ["mock_effect"]

    async def _async_test_effect(name, target=None, called=True):
        async_mocked_start_flow = AsyncMock()
        mocked_bulb.async_start_flow = async_mocked_start_flow
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_EFFECT: name},
            blocking=True,
        )
        if not called:
            return
        async_mocked_start_flow.assert_called_once()
        if target is None:
            return
        args, _ = async_mocked_start_flow.call_args
        flow = args[0]
        assert flow.count == target.count
        assert flow.action == target.action
        assert str(flow.transitions) == str(target.transitions)

    effects = {
        "mock_effect": Flow(
            count=3,
            transitions=[
                HSVTransition(300, 50, 500, 50),
                RGBTransition(100, 100, 100, 300, 30),
                TemperatureTransition(3000, 200, 20),
                SleepTransition(800),
            ],
        ),
        EFFECT_DISCO: Flow(transitions=transitions.disco()),
        EFFECT_FAST_RANDOM_LOOP: None,
        EFFECT_WHATSAPP: Flow(count=2, transitions=transitions.pulse(37, 211, 102)),
        EFFECT_FACEBOOK: Flow(count=2, transitions=transitions.pulse(59, 89, 152)),
        EFFECT_TWITTER: Flow(count=2, transitions=transitions.pulse(0, 172, 237)),
        EFFECT_HOME: Flow(
            count=0,
            action=Action.recover,
            transitions=[
                TemperatureTransition(degrees=3200, duration=500, brightness=80)
            ],
        ),
        EFFECT_NIGHT_MODE: Flow(
            count=0,
            action=Action.recover,
            transitions=[RGBTransition(0xFF, 0x99, 0x00, duration=500, brightness=1)],
        ),
        EFFECT_DATE_NIGHT: Flow(
            count=0,
            action=Action.recover,
            transitions=[RGBTransition(0xFF, 0x66, 0x00, duration=500, brightness=50)],
        ),
        EFFECT_MOVIE: Flow(
            count=0,
            action=Action.recover,
            transitions=[
                RGBTransition(
                    red=0x14, green=0x14, blue=0x32, duration=500, brightness=50
                )
            ],
        ),
        EFFECT_SUNRISE: Flow(
            count=1,
            action=Action.stay,
            transitions=[
                RGBTransition(
                    red=0xFF, green=0x4D, blue=0x00, duration=50, brightness=1
                ),
                TemperatureTransition(degrees=1700, duration=360000, brightness=10),
                TemperatureTransition(degrees=2700, duration=540000, brightness=100),
            ],
        ),
        EFFECT_SUNSET: Flow(
            count=1,
            action=Action.off,
            transitions=[
                TemperatureTransition(degrees=2700, duration=50, brightness=10),
                TemperatureTransition(degrees=1700, duration=180000, brightness=5),
                RGBTransition(
                    red=0xFF, green=0x4C, blue=0x00, duration=420000, brightness=1
                ),
            ],
        ),
        EFFECT_ROMANCE: Flow(
            count=0,
            action=Action.stay,
            transitions=[
                RGBTransition(
                    red=0x59, green=0x15, blue=0x6D, duration=4000, brightness=1
                ),
                RGBTransition(
                    red=0x66, green=0x14, blue=0x2A, duration=4000, brightness=1
                ),
            ],
        ),
        EFFECT_HAPPY_BIRTHDAY: Flow(
            count=0,
            action=Action.stay,
            transitions=[
                RGBTransition(
                    red=0xDC, green=0x50, blue=0x19, duration=1996, brightness=80
                ),
                RGBTransition(
                    red=0xDC, green=0x78, blue=0x1E, duration=1996, brightness=80
                ),
                RGBTransition(
                    red=0xAA, green=0x32, blue=0x14, duration=1996, brightness=80
                ),
            ],
        ),
        EFFECT_CANDLE_FLICKER: Flow(
            count=0,
            action=Action.recover,
            transitions=[
                TemperatureTransition(degrees=2700, duration=800, brightness=50),
                TemperatureTransition(degrees=2700, duration=800, brightness=30),
                TemperatureTransition(degrees=2700, duration=1200, brightness=80),
                TemperatureTransition(degrees=2700, duration=800, brightness=60),
                TemperatureTransition(degrees=2700, duration=1200, brightness=90),
                TemperatureTransition(degrees=2700, duration=2400, brightness=50),
                TemperatureTransition(degrees=2700, duration=1200, brightness=80),
                TemperatureTransition(degrees=2700, duration=800, brightness=60),
                TemperatureTransition(degrees=2700, duration=400, brightness=70),
            ],
        ),
    }

    for name, target in effects.items():
        await _async_test_effect(name, target)
    await _async_test_effect("not_existed", called=False)


async def test_ambilight_with_nightlight_disabled(hass: HomeAssistant):
    """Test that main light on ambilights with the nightlight disabled shows the correct brightness."""
    mocked_bulb = _mocked_bulb()
    properties = {**PROPERTIES}
    capabilities = {**CAPABILITIES}
    capabilities["model"] = "ceiling10"
    properties["color_mode"] = "3"  # HSV
    properties["bg_power"] = "off"
    properties["bg_lmode"] = "2"  # CT
    mocked_bulb.last_properties = properties
    mocked_bulb.bulb_type = BulbType.WhiteTempMood
    main_light_entity_id = "light.yeelight_ceiling10_0x15243f"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: False},
        options={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: False},
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(capabilities=capabilities), patch(
        f"{MODULE}.AsyncBulb", return_value=mocked_bulb
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        # We use asyncio.create_task now to avoid
        # blocking starting so we need to block again
        await hass.async_block_till_done()

    state = hass.states.get(main_light_entity_id)
    assert state.state == "on"
    # bg_power off should not set the brightness to 0
    assert state.attributes[ATTR_BRIGHTNESS] == 128


async def test_state_fails_to_update_triggers_update(hass: HomeAssistant):
    """Ensure we call async_get_properties if the turn on/off fails to update the state."""
    mocked_bulb = _mocked_bulb()
    properties = {**PROPERTIES}
    properties.pop("active_mode")
    properties["color_mode"] = "3"  # HSV
    mocked_bulb.last_properties = properties
    mocked_bulb.bulb_type = BulbType.Color
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: False}
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_discovery_interval(), patch(
        f"{MODULE}.AsyncBulb", return_value=mocked_bulb
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        # We use asyncio.create_task now to avoid
        # blocking starting so we need to block again
        await hass.async_block_till_done()

    assert len(mocked_bulb.async_get_properties.mock_calls) == 1

    mocked_bulb.last_properties["power"] = "off"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
        },
        blocking=True,
    )
    assert len(mocked_bulb.async_turn_on.mock_calls) == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(mocked_bulb.async_get_properties.mock_calls) == 2

    mocked_bulb.last_properties["power"] = "on"
    for _ in range(5):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: ENTITY_LIGHT,
            },
            blocking=True,
        )
    assert len(mocked_bulb.async_turn_off.mock_calls) == 5
    # Even with five calls we only do one state request
    # since each successive call should cancel the unexpected
    # state check
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert len(mocked_bulb.async_get_properties.mock_calls) == 3

    # But if the state is correct no calls
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
        },
        blocking=True,
    )
    assert len(mocked_bulb.async_turn_on.mock_calls) == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    assert len(mocked_bulb.async_get_properties.mock_calls) == 3
