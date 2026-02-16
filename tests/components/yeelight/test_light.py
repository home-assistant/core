"""Test the Yeelight light."""

from datetime import timedelta
import logging
import socket
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion
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

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
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
    ATTR_KELVIN,
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

from . import (
    CAPABILITIES,
    ENTITY_LIGHT,
    ENTITY_NIGHTLIGHT,
    IP_ADDRESS,
    MODULE,
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


async def test_services(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test Yeelight services."""
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
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
    with (
        _patch_discovery(),
        _patch_discovery_interval(),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
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
        elif isinstance(payload, list):
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
    color_temp = 5000
    transition = 1
    mocked_bulb.last_properties["power"] = "off"
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_BRIGHTNESS: brightness,
            ATTR_COLOR_TEMP_KELVIN: color_temp,
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
        color_temp,
        duration=transition * 1000,
        light_type=LightType.Main,
    )
    mocked_bulb.async_set_hsv.assert_not_called()
    mocked_bulb.async_set_rgb.assert_not_called()
    mocked_bulb.async_start_flow.assert_called_once()  # flash
    mocked_bulb.async_stop_flow.assert_called_once_with(light_type=LightType.Main)

    # turn_on color_temp - flash short
    brightness = 100
    color_temp = 5000
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
            ATTR_COLOR_TEMP_KELVIN: color_temp,
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
        color_temp,
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
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
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

    mocked_bulb.async_set_brightness = AsyncMock(side_effect=TimeoutError)
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


async def test_update_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
    with (
        _patch_discovery(),
        _patch_discovery_interval(),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON
    assert hass.states.get(ENTITY_NIGHTLIGHT).state == STATE_OFF

    # Timeout usually means the bulb is overloaded with commands
    # but will still respond eventually.
    mocked_bulb.async_turn_off = AsyncMock(side_effect=TimeoutError)
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


async def test_state_already_set_avoid_ratelimit(hass: HomeAssistant) -> None:
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
    with (
        _patch_discovery(),
        _patch_discovery_interval(),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
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

    # color model needs a workaround (see MODELS_WITH_DELAYED_ON_TRANSITION)
    mocked_bulb.model = "color"
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
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 4000},
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
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 4000},
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
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 4000},
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


@pytest.mark.parametrize(
    (
        "bulb_type",
        "model",
        "name",
        "entity_id",
        "extra_properties",
        "nightlight_entity",
        "nightlight_mode",
    ),
    [
        # Default
        pytest.param(
            None,
            "mono",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "3"},  # HSV
            False,
            False,
            id="default",
        ),
        # White
        pytest.param(
            BulbType.White,
            "mono",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "3"},  # HSV
            False,
            False,
            id="white",
        ),
        # Color - color mode CT
        pytest.param(
            BulbType.Color,
            "color",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "2"},  # CT
            True,
            True,
            id="color_ct",
        ),
        # Color - color mode HS
        pytest.param(
            BulbType.Color,
            "color",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "3"},  # HSV
            True,
            False,
            id="color_hsv",
        ),
        # Color - color mode RGB
        pytest.param(
            BulbType.Color,
            "color",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "1"},  # RGB
            True,
            False,
            id="color_rgb",
        ),
        # Color - color mode HS but no hue
        pytest.param(
            BulbType.Color,
            "color",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "3", "hue": None},  # HSV
            True,
            False,
            id="color_hsv_no_hue",
        ),
        # Color - color mode RGB but no color
        pytest.param(
            BulbType.Color,
            "color",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "1", "rgb": None},  # RGB
            True,
            False,
            id="color_rgb_no_color",
        ),
        # Color - unsupported color_mode
        pytest.param(
            BulbType.Color,
            "color",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on", "color_mode": "4"},  # Unsupported
            True,
            False,
            id="color_unsupported",
        ),
        # WhiteTemp
        pytest.param(
            BulbType.WhiteTemp,
            "ceiling1",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {"power": "on"},
            True,
            True,
            id="whitetemp",
        ),
        # WhiteTempMood
        pytest.param(
            BulbType.WhiteTempMood,
            "ceiling4",
            UNIQUE_FRIENDLY_NAME,
            ENTITY_LIGHT,
            {},
            True,
            True,
            id="whitetempmood",
        ),
        # Background light - color mode CT
        pytest.param(
            BulbType.WhiteTempMood,
            "ceiling4",
            f"{UNIQUE_FRIENDLY_NAME} Ambilight",
            f"{ENTITY_LIGHT}_ambilight",
            {"bg_lmode": "2"},  # CT
            False,
            False,
            id="backgroundlight_ct",
        ),
        # Background light - color mode HS
        pytest.param(
            BulbType.WhiteTempMood,
            "ceiling4",
            f"{UNIQUE_FRIENDLY_NAME} Ambilight",
            f"{ENTITY_LIGHT}_ambilight",
            {"bg_lmode": "3"},  # HS
            False,
            False,
            id="backgroundlight_hs",
        ),
        # Background light - color mode RGB
        pytest.param(
            BulbType.WhiteTempMood,
            "ceiling4",
            f"{UNIQUE_FRIENDLY_NAME} Ambilight",
            f"{ENTITY_LIGHT}_ambilight",
            {"bg_lmode": "1"},  # RGB
            False,
            False,
            id="backgroundlight_rgb",
        ),
    ],
)
async def test_device_types(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
    bulb_type: BulbType | None,
    model: str,
    name: str,
    entity_id: str,
    extra_properties: dict[str, Any],
    nightlight_entity: bool,
    nightlight_mode: bool,
    request: pytest.FixtureRequest,
) -> None:
    """Test different device types."""
    mocked_bulb = _mocked_bulb()
    properties = {**PROPERTIES}
    properties.pop("active_mode")
    properties.pop("power")
    properties.update(extra_properties)
    mocked_bulb.last_properties = properties

    async def _async_setup(config_entry: MockConfigEntry) -> None:
        with _patch_discovery(), patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb):
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            # We use asyncio.create_task now to avoid
            # blocking starting so we need to block again
            await hass.async_block_till_done()

    async def _async_test(
        bulb_type: BulbType | None,
        model: str,
        *,
        nightlight_entity_properties: bool,
        name: str,
        entity_id: str,
        nightlight_mode_properties: bool,
    ) -> None:
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
        assert state.attributes == snapshot
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.config_entries.async_remove(config_entry.entry_id)
        entity_registry.async_clear_config_entry(config_entry.entry_id)
        mocked_bulb.last_properties["nl_br"] = original_nightlight_brightness

        # nightlight as a setting of the main entity
        if nightlight_mode_properties:
            mocked_bulb.last_properties["active_mode"] = True
            config_entry = MockConfigEntry(
                domain=DOMAIN, data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: False}
            )
            config_entry.add_to_hass(hass)
            await _async_setup(config_entry)
            state = hass.states.get(entity_id)
            assert state.state == "on"
            assert state.attributes == snapshot(
                name=f"{request.node.callspec.id}_nightlight_mode"
            )

            await hass.config_entries.async_unload(config_entry.entry_id)
            await hass.config_entries.async_remove(config_entry.entry_id)
            entity_registry.async_clear_config_entry(config_entry.entry_id)
            await hass.async_block_till_done()
            mocked_bulb.last_properties.pop("active_mode")

        # nightlight as a separate entity
        if nightlight_entity_properties:
            config_entry = MockConfigEntry(
                domain=DOMAIN, data={**CONFIG_ENTRY_DATA, CONF_NIGHTLIGHT_SWITCH: True}
            )
            config_entry.add_to_hass(hass)
            await _async_setup(config_entry)

            assert hass.states.get(entity_id).state == "off"
            state = hass.states.get(f"{entity_id}_nightlight")
            assert state.state == "on"
            assert state.attributes == snapshot(
                name=f"{request.node.callspec.id}_nightlight_entity"
            )

            await hass.config_entries.async_unload(config_entry.entry_id)
            await hass.config_entries.async_remove(config_entry.entry_id)
            entity_registry.async_clear_config_entry(config_entry.entry_id)
            await hass.async_block_till_done()

    await _async_test(
        bulb_type,
        model,
        name=name,
        entity_id=entity_id,
        nightlight_entity_properties=nightlight_entity,
        nightlight_mode_properties=nightlight_mode,
    )
    assert ("Light reported unknown color mode: 4" in caplog.text) == (
        request.node.callspec.id == "color_unsupported"
    )


async def test_effects(hass: HomeAssistant) -> None:
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
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with (
        _patch_discovery(),
        _patch_discovery_interval(),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).attributes.get("effect_list") == [
        *YEELIGHT_COLOR_EFFECT_LIST,
        "mock_effect",
    ]

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


async def test_ambilight_with_nightlight_disabled(hass: HomeAssistant) -> None:
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
    with (
        _patch_discovery(capabilities=capabilities),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
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


async def test_state_fails_to_update_triggers_update(hass: HomeAssistant) -> None:
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
    with (
        _patch_discovery(),
        _patch_discovery_interval(),
        patch(f"{MODULE}.AsyncBulb", return_value=mocked_bulb),
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
