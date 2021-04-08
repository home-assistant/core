"""Test the Yeelight light."""
import logging
from unittest.mock import MagicMock, patch

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
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    FLASH_LONG,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.yeelight import (
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
    SUPPORT_YEELIGHT,
    SUPPORT_YEELIGHT_RGB,
    SUPPORT_YEELIGHT_WHITE_TEMP,
    YEELIGHT_COLOR_EFFECT_LIST,
    YEELIGHT_MONO_EFFECT_LIST,
    YEELIGHT_TEMP_ONLY_EFFECT_LIST,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_hs_to_xy,
    color_RGB_to_hs,
    color_RGB_to_xy,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import (
    ENTITY_LIGHT,
    ENTITY_NIGHTLIGHT,
    IP_ADDRESS,
    MODULE,
    NAME,
    PROPERTIES,
    UNIQUE_NAME,
    _mocked_bulb,
    _patch_discovery,
)

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {
    CONF_HOST: IP_ADDRESS,
    CONF_TRANSITION: DEFAULT_TRANSITION,
    CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
    CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
    CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
}


async def test_services(hass: HomeAssistant, caplog):
    """Test Yeelight services."""
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
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    async def _async_test_service(
        service,
        data,
        method,
        payload=None,
        domain=DOMAIN,
        failure_side_effect=BulbException,
    ):
        err_count = len([x for x in caplog.records if x.levelno == logging.ERROR])

        # success
        mocked_method = MagicMock()
        setattr(type(mocked_bulb), method, mocked_method)
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
            mocked_method = MagicMock(side_effect=failure_side_effect)
            setattr(type(mocked_bulb), method, mocked_method)
            await hass.services.async_call(domain, service, data, blocking=True)
            assert (
                len([x for x in caplog.records if x.levelno == logging.ERROR])
                == err_count + 1
            )

    # turn_on
    brightness = 100
    color_temp = 200
    transition = 1
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
    mocked_bulb.turn_on.assert_called_once_with(
        duration=transition * 1000,
        light_type=LightType.Main,
        power_mode=PowerMode.NORMAL,
    )
    mocked_bulb.turn_on.reset_mock()
    mocked_bulb.start_music.assert_called_once()
    mocked_bulb.set_brightness.assert_called_once_with(
        brightness / 255 * 100, duration=transition * 1000, light_type=LightType.Main
    )
    mocked_bulb.set_color_temp.assert_called_once_with(
        color_temperature_mired_to_kelvin(color_temp),
        duration=transition * 1000,
        light_type=LightType.Main,
    )
    mocked_bulb.start_flow.assert_called_once()  # flash
    mocked_bulb.stop_flow.assert_called_once_with(light_type=LightType.Main)

    # turn_on nightlight
    await _async_test_service(
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_NIGHTLIGHT},
        "turn_on",
        payload={
            "duration": DEFAULT_TRANSITION,
            "light_type": LightType.Main,
            "power_mode": PowerMode.MOONLIGHT,
        },
        domain="light",
    )

    # turn_off
    await _async_test_service(
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_TRANSITION: transition},
        "turn_off",
        domain="light",
        payload={"duration": transition * 1000, "light_type": LightType.Main},
    )

    # set_mode
    mode = "rgb"
    await _async_test_service(
        SERVICE_SET_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE: "rgb"},
        "set_power_mode",
        [PowerMode[mode.upper()]],
    )

    # start_flow
    await _async_test_service(
        SERVICE_START_FLOW,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_TRANSITIONS: [{YEELIGHT_TEMPERATURE_TRANSACTION: [1900, 2000, 60]}],
        },
        "start_flow",
    )

    # set_color_scene
    await _async_test_service(
        SERVICE_SET_COLOR_SCENE,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_RGB_COLOR: [10, 20, 30],
            ATTR_BRIGHTNESS: 50,
        },
        "set_scene",
        [SceneClass.COLOR, 10, 20, 30, 50],
    )

    # set_hsv_scene
    await _async_test_service(
        SERVICE_SET_HSV_SCENE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_HS_COLOR: [180, 50], ATTR_BRIGHTNESS: 50},
        "set_scene",
        [SceneClass.HSV, 180, 50, 50],
    )

    # set_color_temp_scene
    await _async_test_service(
        SERVICE_SET_COLOR_TEMP_SCENE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_KELVIN: 4000, ATTR_BRIGHTNESS: 50},
        "set_scene",
        [SceneClass.CT, 4000, 50],
    )

    # set_color_flow_scene
    await _async_test_service(
        SERVICE_SET_COLOR_FLOW_SCENE,
        {
            ATTR_ENTITY_ID: ENTITY_LIGHT,
            ATTR_TRANSITIONS: [{YEELIGHT_TEMPERATURE_TRANSACTION: [1900, 2000, 60]}],
        },
        "set_scene",
    )

    # set_auto_delay_off_scene
    await _async_test_service(
        SERVICE_SET_AUTO_DELAY_OFF_SCENE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MINUTES: 1, ATTR_BRIGHTNESS: 50},
        "set_scene",
        [SceneClass.AUTO_DELAY_OFF, 50, 1],
    )

    # set_music_mode failure enable
    await _async_test_service(
        SERVICE_SET_MUSIC_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE_MUSIC: "true"},
        "start_music",
        failure_side_effect=AssertionError,
    )

    # set_music_mode disable
    await _async_test_service(
        SERVICE_SET_MUSIC_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE_MUSIC: "false"},
        "stop_music",
        failure_side_effect=None,
    )

    # set_music_mode success enable
    await _async_test_service(
        SERVICE_SET_MUSIC_MODE,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_MODE_MUSIC: "true"},
        "start_music",
        failure_side_effect=None,
    )
    # test _cmd wrapper error handler
    err_count = len([x for x in caplog.records if x.levelno == logging.ERROR])
    type(mocked_bulb).turn_on = MagicMock()
    type(mocked_bulb).set_brightness = MagicMock(side_effect=BulbException)
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 50},
        blocking=True,
    )
    assert (
        len([x for x in caplog.records if x.levelno == logging.ERROR]) == err_count + 1
    )


async def test_device_types(hass: HomeAssistant):
    """Test different device types."""
    mocked_bulb = _mocked_bulb()
    properties = {**PROPERTIES}
    properties.pop("active_mode")
    properties["color_mode"] = "3"
    mocked_bulb.last_properties = properties

    async def _async_setup(config_entry):
        with patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    async def _async_test(
        bulb_type,
        model,
        target_properties,
        nightlight_properties=None,
        name=UNIQUE_NAME,
        entity_id=ENTITY_LIGHT,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                **CONFIG_ENTRY_DATA,
                CONF_NIGHTLIGHT_SWITCH: False,
            },
        )
        config_entry.add_to_hass(hass)

        mocked_bulb.bulb_type = bulb_type
        model_specs = _MODEL_SPECS.get(model)
        type(mocked_bulb).get_model_specs = MagicMock(return_value=model_specs)
        await _async_setup(config_entry)

        state = hass.states.get(entity_id)
        assert state.state == "on"
        target_properties["friendly_name"] = name
        target_properties["flowing"] = False
        target_properties["night_light"] = True
        target_properties["music_mode"] = False
        assert dict(state.attributes) == target_properties

        await hass.config_entries.async_unload(config_entry.entry_id)
        await config_entry.async_remove(hass)
        registry = er.async_get(hass)
        registry.async_clear_config_entry(config_entry.entry_id)

        # nightlight
        if nightlight_properties is None:
            return
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                **CONFIG_ENTRY_DATA,
                CONF_NIGHTLIGHT_SWITCH: True,
            },
        )
        config_entry.add_to_hass(hass)
        await _async_setup(config_entry)

        assert hass.states.get(entity_id).state == "off"
        state = hass.states.get(f"{entity_id}_nightlight")
        assert state.state == "on"
        nightlight_properties["friendly_name"] = f"{name} nightlight"
        nightlight_properties["icon"] = "mdi:weather-night"
        nightlight_properties["flowing"] = False
        nightlight_properties["night_light"] = True
        nightlight_properties["music_mode"] = False
        assert dict(state.attributes) == nightlight_properties

        await hass.config_entries.async_unload(config_entry.entry_id)
        await config_entry.async_remove(hass)
        registry.async_clear_config_entry(config_entry.entry_id)

    bright = round(255 * int(PROPERTIES["bright"]) / 100)
    current_brightness = round(255 * int(PROPERTIES["current_brightness"]) / 100)
    ct = color_temperature_kelvin_to_mired(int(PROPERTIES["ct"]))
    hue = int(PROPERTIES["hue"])
    sat = int(PROPERTIES["sat"])
    hs_color = (round(hue / 360 * 65536, 3), round(sat / 100 * 255, 3))
    rgb_color = color_hs_to_RGB(*hs_color)
    xy_color = color_hs_to_xy(*hs_color)
    bg_bright = round(255 * int(PROPERTIES["bg_bright"]) / 100)
    bg_ct = color_temperature_kelvin_to_mired(int(PROPERTIES["bg_ct"]))
    bg_rgb = int(PROPERTIES["bg_rgb"])
    bg_rgb_color = ((bg_rgb >> 16) & 0xFF, (bg_rgb >> 8) & 0xFF, bg_rgb & 0xFF)
    bg_hs_color = color_RGB_to_hs(*bg_rgb_color)
    bg_xy_color = color_RGB_to_xy(*bg_rgb_color)
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

    # Color
    model_specs = _MODEL_SPECS["color"]
    await _async_test(
        BulbType.Color,
        "color",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT_RGB,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": current_brightness,
            "color_temp": ct,
            "hs_color": hs_color,
            "rgb_color": rgb_color,
            "xy_color": xy_color,
            "color_mode": "hs",
            "supported_color_modes": ["color_temp", "hs"],
        },
        {
            "supported_features": 0,
            "color_mode": "onoff",
            "supported_color_modes": ["onoff"],
        },
    )

    # WhiteTemp
    model_specs = _MODEL_SPECS["ceiling1"]
    await _async_test(
        BulbType.WhiteTemp,
        "ceiling1",
        {
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT_WHITE_TEMP,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": current_brightness,
            "color_temp": ct,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp"],
        },
        {
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "brightness": nl_br,
            "color_mode": "brightness",
            "supported_color_modes": ["brightness"],
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
            "supported_features": SUPPORT_YEELIGHT_WHITE_TEMP,
            "min_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["max"]
            ),
            "max_mireds": color_temperature_kelvin_to_mired(
                model_specs["color_temp"]["min"]
            ),
            "brightness": current_brightness,
            "color_temp": ct,
            "color_mode": "color_temp",
            "supported_color_modes": ["color_temp"],
        },
        {
            "effect_list": YEELIGHT_TEMP_ONLY_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT,
            "brightness": nl_br,
            "color_mode": "brightness",
            "supported_color_modes": ["brightness"],
        },
    )
    await _async_test(
        BulbType.WhiteTempMood,
        "ceiling4",
        {
            "effect_list": YEELIGHT_COLOR_EFFECT_LIST,
            "supported_features": SUPPORT_YEELIGHT_RGB,
            "min_mireds": color_temperature_kelvin_to_mired(6500),
            "max_mireds": color_temperature_kelvin_to_mired(1700),
            "brightness": bg_bright,
            "color_temp": bg_ct,
            "hs_color": bg_hs_color,
            "rgb_color": bg_rgb_color,
            "xy_color": bg_xy_color,
            "color_mode": "hs",
            "supported_color_modes": ["color_temp", "hs"],
        },
        name=f"{UNIQUE_NAME} ambilight",
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
                    },
                ],
            },
        },
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA,
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).attributes.get(
        "effect_list"
    ) == YEELIGHT_COLOR_EFFECT_LIST + ["mock_effect"]

    async def _async_test_effect(name, target=None, called=True):
        mocked_start_flow = MagicMock()
        type(mocked_bulb).start_flow = mocked_start_flow
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_EFFECT: name},
            blocking=True,
        )
        if not called:
            return
        mocked_start_flow.assert_called_once()
        if target is None:
            return
        args, _ = mocked_start_flow.call_args
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
