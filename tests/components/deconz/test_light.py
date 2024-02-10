"""deCONZ light platform tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.deconz.const import ATTR_ON, CONF_ALLOW_DECONZ_GROUPS
from homeassistant.components.deconz.light import DECONZ_GROUP
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_COLORLOOP,
    FLASH_LONG,
    FLASH_SHORT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_no_lights_or_groups(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that no lights or groups entities are created."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (  # RGB light in color temp color mode
            {
                "colorcapabilities": 31,
                "ctmax": 500,
                "ctmin": 153,
                "etag": "055485a82553e654f156d41c9301b7cf",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2021-06-10T20:25Z",
                "manufacturername": "Philips",
                "modelid": "LLC020",
                "name": "Hue Go",
                "state": {
                    "alert": "none",
                    "bri": 254,
                    "colormode": "ct",
                    "ct": 375,
                    "effect": "none",
                    "hue": 8348,
                    "on": True,
                    "reachable": True,
                    "sat": 147,
                    "xy": [0.462, 0.4111],
                },
                "swversion": "5.127.1.26420",
                "type": "Extended color light",
                "uniqueid": "00:17:88:01:01:23:45:67-00",
            },
            {
                "entity_id": "light.hue_go",
                "state": STATE_ON,
                "attributes": {
                    ATTR_BRIGHTNESS: 254,
                    ATTR_COLOR_TEMP: 375,
                    ATTR_EFFECT_LIST: [EFFECT_COLORLOOP],
                    ATTR_SUPPORTED_COLOR_MODES: [
                        ColorMode.COLOR_TEMP,
                        ColorMode.HS,
                        ColorMode.XY,
                    ],
                    ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
                    ATTR_MIN_MIREDS: 153,
                    ATTR_MAX_MIREDS: 500,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH
                    | LightEntityFeature.EFFECT,
                    DECONZ_GROUP: False,
                },
            },
        ),
        (  # RGB light in XY color mode
            {
                "colorcapabilities": 0,
                "ctmax": 65535,
                "ctmin": 0,
                "etag": "74c91da78bbb5f4dc4d36edf4ad6857c",
                "hascolor": True,
                "lastannounced": "2021-01-27T18:05:38Z",
                "lastseen": "2021-06-10T20:26Z",
                "manufacturername": "Philips",
                "modelid": "4090331P9_01",
                "name": "Hue Ensis",
                "state": {
                    "alert": "none",
                    "bri": 254,
                    "colormode": "xy",
                    "ct": 316,
                    "effect": "0",
                    "hue": 3096,
                    "on": True,
                    "reachable": True,
                    "sat": 48,
                    "xy": [0.427, 0.373],
                },
                "swversion": "1.65.9_hB3217DF4",
                "type": "Extended color light",
                "uniqueid": "00:17:88:01:01:23:45:67-01",
            },
            {
                "entity_id": "light.hue_ensis",
                "state": STATE_ON,
                "attributes": {
                    ATTR_MIN_MIREDS: 140,
                    ATTR_MAX_MIREDS: 650,
                    ATTR_EFFECT_LIST: [EFFECT_COLORLOOP],
                    ATTR_SUPPORTED_COLOR_MODES: [
                        ColorMode.COLOR_TEMP,
                        ColorMode.HS,
                        ColorMode.XY,
                    ],
                    ATTR_COLOR_MODE: ColorMode.XY,
                    ATTR_BRIGHTNESS: 254,
                    ATTR_HS_COLOR: (29.691, 38.039),
                    ATTR_RGB_COLOR: (255, 206, 158),
                    ATTR_XY_COLOR: (0.427, 0.373),
                    DECONZ_GROUP: False,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH
                    | LightEntityFeature.EFFECT,
                },
            },
        ),
        (  # RGB light with only HS color mode
            {
                "etag": "87a89542bf9b9d0aa8134919056844f8",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2020-12-05T22:57Z",
                "manufacturername": "_TZE200_s8gkrkxk",
                "modelid": "TS0601",
                "name": "LIDL xmas light",
                "state": {
                    "bri": 25,
                    "colormode": "hs",
                    "effect": "none",
                    "hue": 53691,
                    "on": True,
                    "reachable": True,
                    "sat": 141,
                },
                "swversion": None,
                "type": "Color dimmable light",
                "uniqueid": "58:8e:81:ff:fe:db:7b:be-01",
            },
            {
                "entity_id": "light.lidl_xmas_light",
                "state": STATE_ON,
                "attributes": {
                    ATTR_EFFECT_LIST: [
                        "carnival",
                        "collide",
                        "fading",
                        "fireworks",
                        "flag",
                        "glow",
                        "rainbow",
                        "snake",
                        "snow",
                        "sparkles",
                        "steady",
                        "strobe",
                        "twinkle",
                        "updown",
                        "vintage",
                        "waves",
                    ],
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
                    ATTR_COLOR_MODE: ColorMode.HS,
                    ATTR_BRIGHTNESS: 25,
                    ATTR_HS_COLOR: (294.938, 55.294),
                    ATTR_RGB_COLOR: (243, 113, 255),
                    ATTR_XY_COLOR: (0.357, 0.188),
                    DECONZ_GROUP: False,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH
                    | LightEntityFeature.EFFECT,
                },
            },
        ),
        (  # Tunable white light in CT color mode
            {
                "colorcapabilities": 16,
                "ctmax": 454,
                "ctmin": 153,
                "etag": "576ffecbedb4abdc3d3f375fd8f17a9e",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2021-06-10T20:25Z",
                "manufacturername": "Philips",
                "modelid": "LTW013",
                "name": "Hue White Ambiance",
                "state": {
                    "alert": "none",
                    "bri": 254,
                    "colormode": "ct",
                    "ct": 396,
                    "on": True,
                    "reachable": True,
                },
                "swversion": "1.46.13_r26312",
                "type": "Color temperature light",
                "uniqueid": "00:17:88:01:01:23:45:67-02",
            },
            {
                "entity_id": "light.hue_white_ambiance",
                "state": STATE_ON,
                "attributes": {
                    ATTR_MIN_MIREDS: 153,
                    ATTR_MAX_MIREDS: 454,
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
                    ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
                    ATTR_BRIGHTNESS: 254,
                    ATTR_COLOR_TEMP: 396,
                    DECONZ_GROUP: False,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH,
                },
            },
        ),
        (  # Dimmable light
            {
                "etag": "f88e87235e2abce62404edd99b1af323",
                "hascolor": False,
                "lastannounced": None,
                "lastseen": "2021-06-10T20:26Z",
                "manufacturername": "Philips",
                "modelid": "LWO001",
                "name": "Hue Filament",
                "state": {"alert": "none", "bri": 254, "on": True, "reachable": True},
                "swversion": "1.55.8_r28815",
                "type": "Dimmable light",
                "uniqueid": "00:17:88:01:01:23:45:67-03",
            },
            {
                "entity_id": "light.hue_filament",
                "state": STATE_ON,
                "attributes": {
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
                    ATTR_COLOR_MODE: ColorMode.BRIGHTNESS,
                    ATTR_BRIGHTNESS: 254,
                    DECONZ_GROUP: False,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH,
                },
            },
        ),
        (  # On/Off light
            {
                "etag": "99c67fd8f0529c6c2aab94b45e4f6caa",
                "hascolor": False,
                "lastannounced": "2021-04-26T20:28:11Z",
                "lastseen": "2021-06-10T21:15Z",
                "manufacturername": "Unknown",
                "modelid": "Unknown",
                "name": "Simple Light",
                "state": {"alert": "none", "on": True, "reachable": True},
                "swversion": "2.0",
                "type": "Simple light",
                "uniqueid": "00:15:8d:00:01:23:45:67-01",
            },
            {
                "entity_id": "light.simple_light",
                "state": STATE_ON,
                "attributes": {
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF],
                    ATTR_COLOR_MODE: ColorMode.ONOFF,
                    DECONZ_GROUP: False,
                    ATTR_SUPPORTED_FEATURES: 0,
                },
            },
        ),
    ],
)
async def test_lights(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, input, expected
) -> None:
    """Test that different light entities are created with expected values."""
    data = {"lights": {"0": input}}
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1

    light = hass.states.get(expected["entity_id"])
    assert light.state == expected["state"]
    for attribute, expected_value in expected["attributes"].items():
        assert light.attributes[attribute] == expected_value

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_light_state_change(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_deconz_websocket
) -> None:
    """Verify light can change state on websocket event."""
    data = {
        "lights": {
            "0": {
                "colorcapabilities": 31,
                "ctmax": 500,
                "ctmin": 153,
                "etag": "055485a82553e654f156d41c9301b7cf",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2021-06-10T20:25Z",
                "manufacturername": "Philips",
                "modelid": "LLC020",
                "name": "Hue Go",
                "state": {
                    "alert": "none",
                    "bri": 254,
                    "colormode": "ct",
                    "ct": 375,
                    "effect": "none",
                    "hue": 8348,
                    "on": True,
                    "reachable": True,
                    "sat": 147,
                    "xy": [0.462, 0.4111],
                },
                "swversion": "5.127.1.26420",
                "type": "Extended color light",
                "uniqueid": "00:17:88:01:01:23:45:67-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert hass.states.get("light.hue_go").state == STATE_ON

    event_changed_light = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "0",
        "state": {"on": False},
    }
    await mock_deconz_websocket(data=event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("light.hue_go").state == STATE_OFF


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (  # Turn on light with hue and sat
            {
                "light_on": True,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_HS_COLOR: (20, 30),
                },
            },
            {
                "on": True,
                "xy": (0.411, 0.351),
            },
        ),
        (  # Turn on light with XY color
            {
                "light_on": True,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_XY_COLOR: (0.411, 0.351),
                },
            },
            {
                "on": True,
                "xy": (0.411, 0.351),
            },
        ),
        (  # Turn on light without transition time
            {
                "light_on": True,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_TRANSITION: 0,
                },
            },
            {
                "on": True,
                "transitiontime": 0,
            },
        ),
        (  # Turn on light with short color loop
            {
                "light_on": False,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_BRIGHTNESS: 200,
                    ATTR_COLOR_TEMP: 200,
                    ATTR_TRANSITION: 5,
                    ATTR_FLASH: FLASH_SHORT,
                    ATTR_EFFECT: EFFECT_COLORLOOP,
                },
            },
            {
                "bri": 200,
                "ct": 200,
                "transitiontime": 50,
                "alert": "select",
                "effect": "colorloop",
            },
        ),
        (  # Turn on light disabling color loop with long flashing
            {
                "light_on": False,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_XY_COLOR: (0.411, 0.351),
                    ATTR_FLASH: FLASH_LONG,
                    ATTR_EFFECT: "None",
                },
            },
            {
                "xy": (0.411, 0.351),
                "alert": "lselect",
                "effect": "none",
            },
        ),
        (  # Turn off light with short flashing
            {
                "light_on": True,
                "service": SERVICE_TURN_OFF,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_TRANSITION: 5,
                    ATTR_FLASH: FLASH_SHORT,
                },
            },
            {
                "bri": 0,
                "transitiontime": 50,
                "alert": "select",
            },
        ),
        (  # Turn off light without transition time
            {
                "light_on": True,
                "service": SERVICE_TURN_OFF,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_TRANSITION: 0,
                    ATTR_FLASH: FLASH_SHORT,
                },
            },
            {
                "bri": 0,
                "transitiontime": 0,
                "alert": "select",
            },
        ),
        (  # Turn off light with long flashing
            {
                "light_on": True,
                "service": SERVICE_TURN_OFF,
                "call": {ATTR_ENTITY_ID: "light.hue_go", ATTR_FLASH: FLASH_LONG},
            },
            {"alert": "lselect"},
        ),
        (  # Turn off light when light is already off is not supported
            {
                "light_on": False,
                "service": SERVICE_TURN_OFF,
                "call": {
                    ATTR_ENTITY_ID: "light.hue_go",
                    ATTR_TRANSITION: 5,
                    ATTR_FLASH: FLASH_SHORT,
                },
            },
            {},
        ),
    ],
)
async def test_light_service_calls(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, input, expected
) -> None:
    """Verify light can change state on websocket event."""
    data = {
        "lights": {
            "0": {
                "colorcapabilities": 31,
                "ctmax": 500,
                "ctmin": 153,
                "etag": "055485a82553e654f156d41c9301b7cf",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2021-06-10T20:25Z",
                "manufacturername": "Philips",
                "modelid": "LLC020",
                "name": "Hue Go",
                "state": {
                    "alert": "none",
                    "bri": 254,
                    "colormode": "ct",
                    "ct": 375,
                    "effect": "none",
                    "hue": 8348,
                    "on": input["light_on"],
                    "reachable": True,
                    "sat": 147,
                    "xy": [0.462, 0.4111],
                },
                "swversion": "5.127.1.26420",
                "type": "Extended color light",
                "uniqueid": "00:17:88:01:01:23:45:67-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/0/state")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        input["service"],
        input["call"],
        blocking=True,
    )
    if expected:
        assert aioclient_mock.mock_calls[1][2] == expected
    else:
        assert len(aioclient_mock.mock_calls) == 1  # not called


async def test_ikea_default_transition_time(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify that service calls to IKEA lights always extend with transition tinme 0 if absent."""
    data = {
        "lights": {
            "0": {
                "colorcapabilities": 0,
                "ctmax": 65535,
                "ctmin": 0,
                "etag": "9dd510cd474791481f189d2a68a3c7f1",
                "hascolor": True,
                "lastannounced": "2020-12-17T17:44:38Z",
                "lastseen": "2021-01-11T18:36Z",
                "manufacturername": "IKEA of Sweden",
                "modelid": "TRADFRI bulb E27 WS opal 1000lm",
                "name": "IKEA light",
                "state": {
                    "alert": "none",
                    "bri": 156,
                    "colormode": "ct",
                    "ct": 250,
                    "on": True,
                    "reachable": True,
                },
                "swversion": "2.0.022",
                "type": "Color temperature light",
                "uniqueid": "ec:1b:bd:ff:fe:ee:ed:dd-01",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/0/state")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.ikea_light",
            ATTR_BRIGHTNESS: 100,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {
        "bri": 100,
        "on": True,
        "transitiontime": 0,
    }

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.ikea_light",
            ATTR_BRIGHTNESS: 100,
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {
        "bri": 100,
        "on": True,
        "transitiontime": 50,
    }


async def test_lidl_christmas_light(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that lights or groups entities are created."""
    data = {
        "lights": {
            "0": {
                "etag": "87a89542bf9b9d0aa8134919056844f8",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2020-12-05T22:57Z",
                "manufacturername": "_TZE200_s8gkrkxk",
                "modelid": "TS0601",
                "name": "LIDL xmas light",
                "state": {
                    "bri": 25,
                    "colormode": "hs",
                    "effect": "none",
                    "hue": 53691,
                    "on": True,
                    "reachable": True,
                    "sat": 141,
                },
                "swversion": None,
                "type": "Color dimmable light",
                "uniqueid": "58:8e:81:ff:fe:db:7b:be-01",
            }
        }
    }

    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/0/state")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.lidl_xmas_light",
            ATTR_HS_COLOR: (20, 30),
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "hue": 3640, "sat": 76}

    assert hass.states.get("light.lidl_xmas_light")


async def test_configuration_tool(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify that configuration tool is not created."""
    data = {
        "lights": {
            "0": {
                "etag": "26839cb118f5bf7ba1f2108256644010",
                "hascolor": False,
                "lastannounced": None,
                "lastseen": "2020-11-22T11:27Z",
                "manufacturername": "dresden elektronik",
                "modelid": "ConBee II",
                "name": "Configuration tool 1",
                "state": {"reachable": True},
                "swversion": "0x264a0700",
                "type": "Configuration tool",
                "uniqueid": "00:21:2e:ff:ff:05:a7:a3-01",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (
            {
                "lights": ["1", "2", "3"],
            },
            {
                "entity_id": "light.group",
                "state": ATTR_ON,
                "attributes": {
                    ATTR_MIN_MIREDS: 153,
                    ATTR_MAX_MIREDS: 500,
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP, ColorMode.XY],
                    ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
                    ATTR_BRIGHTNESS: 255,
                    ATTR_EFFECT_LIST: [EFFECT_COLORLOOP],
                    "all_on": False,
                    DECONZ_GROUP: True,
                    ATTR_SUPPORTED_FEATURES: 44,
                },
            },
        ),
        (
            {
                "lights": ["3", "1", "2"],
            },
            {
                "entity_id": "light.group",
                "state": ATTR_ON,
                "attributes": {
                    ATTR_MIN_MIREDS: 153,
                    ATTR_MAX_MIREDS: 500,
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP, ColorMode.XY],
                    ATTR_COLOR_MODE: ColorMode.COLOR_TEMP,
                    ATTR_BRIGHTNESS: 50,
                    ATTR_EFFECT_LIST: [EFFECT_COLORLOOP],
                    "all_on": False,
                    DECONZ_GROUP: True,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH
                    | LightEntityFeature.EFFECT,
                },
            },
        ),
        (
            {
                "lights": ["2", "3", "1"],
            },
            {
                "entity_id": "light.group",
                "state": ATTR_ON,
                "attributes": {
                    ATTR_MIN_MIREDS: 153,
                    ATTR_MAX_MIREDS: 500,
                    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP, ColorMode.XY],
                    ATTR_COLOR_MODE: ColorMode.XY,
                    ATTR_HS_COLOR: (52.0, 100.0),
                    ATTR_RGB_COLOR: (255, 221, 0),
                    ATTR_XY_COLOR: (0.5, 0.5),
                    "all_on": False,
                    DECONZ_GROUP: True,
                    ATTR_SUPPORTED_FEATURES: LightEntityFeature.TRANSITION
                    | LightEntityFeature.FLASH
                    | LightEntityFeature.EFFECT,
                },
            },
        ),
    ],
)
async def test_groups(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, input, expected
) -> None:
    """Test that different group entities are created with expected values."""
    data = {
        "groups": {
            "0": {
                "id": "Light group id",
                "name": "Group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {
                    "alert": "none",
                    "bri": 127,
                    "colormode": "hs",
                    "ct": 0,
                    "effect": "none",
                    "hue": 0,
                    "on": True,
                    "sat": 127,
                    "scene": None,
                    "xy": [0, 0],
                },
                "scenes": [],
                "lights": input["lights"],
            },
        },
        "lights": {
            "1": {
                "name": "RGB light",
                "state": {
                    "on": True,
                    "bri": 50,
                    "colormode": "xy",
                    "effect": "colorloop",
                    "xy": (0.5, 0.5),
                    "reachable": True,
                },
                "type": "Extended color light",
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "ctmax": 454,
                "ctmin": 155,
                "name": "Tunable white light",
                "state": {
                    "on": True,
                    "colormode": "ct",
                    "ct": 2500,
                    "reachable": True,
                },
                "type": "Tunable white light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "3": {
                "name": "Dimmable light",
                "type": "Dimmable light",
                "state": {"bri": 255, "on": True, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 4

    group = hass.states.get(expected["entity_id"])
    assert group.state == expected["state"]
    for attribute, expected_value in expected["attributes"].items():
        assert group.attributes[attribute] == expected_value

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (  # Turn on group with short color loop
            {
                "lights": ["1", "2", "3"],
                "group_on": False,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.group",
                    ATTR_BRIGHTNESS: 200,
                    ATTR_COLOR_TEMP: 200,
                    ATTR_TRANSITION: 5,
                    ATTR_FLASH: FLASH_SHORT,
                    ATTR_EFFECT: EFFECT_COLORLOOP,
                },
            },
            {
                "bri": 200,
                "ct": 200,
                "transitiontime": 50,
                "alert": "select",
                "effect": "colorloop",
            },
        ),
        (  # Turn on group with hs colors
            {
                "lights": ["1", "2", "3"],
                "group_on": False,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.group",
                    ATTR_HS_COLOR: (250, 50),
                },
            },
            {
                "on": True,
                "xy": (0.235, 0.164),
            },
        ),
        (  # Turn on group with short color loop
            {
                "lights": ["3", "2", "1"],
                "group_on": False,
                "service": SERVICE_TURN_ON,
                "call": {
                    ATTR_ENTITY_ID: "light.group",
                    ATTR_HS_COLOR: (250, 50),
                },
            },
            {
                "on": True,
                "xy": (0.235, 0.164),
            },
        ),
    ],
)
async def test_group_service_calls(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, input, expected
) -> None:
    """Verify expected group web request from different service calls."""
    data = {
        "groups": {
            "0": {
                "id": "Light group id",
                "name": "Group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": input["group_on"]},
                "action": {},
                "scenes": [],
                "lights": input["lights"],
            },
        },
        "lights": {
            "1": {
                "name": "RGB light",
                "state": {
                    "bri": 255,
                    "colormode": "xy",
                    "effect": "colorloop",
                    "hue": 53691,
                    "on": True,
                    "reachable": True,
                    "sat": 141,
                    "xy": (0.5, 0.5),
                },
                "type": "Extended color light",
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "ctmax": 454,
                "ctmin": 155,
                "name": "Tunable white light",
                "state": {
                    "on": True,
                    "colormode": "ct",
                    "ct": 2500,
                    "reachable": True,
                },
                "type": "Tunable white light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "3": {
                "name": "Dimmable light",
                "type": "Dimmable light",
                "state": {"bri": 254, "on": True, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/groups/0/action")

    await hass.services.async_call(
        LIGHT_DOMAIN,
        input["service"],
        input["call"],
        blocking=True,
    )
    if expected:
        assert aioclient_mock.mock_calls[1][2] == expected
    else:
        assert len(aioclient_mock.mock_calls) == 1  # not called


async def test_empty_group(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify that a group without a list of lights is not created."""
    data = {
        "groups": {
            "0": {
                "id": "Empty group id",
                "name": "Empty group",
                "type": "LightGroup",
                "state": {},
                "action": {},
                "scenes": [],
                "lights": [],
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("light.empty_group")


async def test_disable_light_groups(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test disallowing light groups work."""
    data = {
        "groups": {
            "1": {
                "id": "Light group id",
                "name": "Light group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {},
                "scenes": [],
                "lights": ["1"],
            },
            "2": {
                "id": "Empty group id",
                "name": "Empty group",
                "type": "LightGroup",
                "state": {},
                "action": {},
                "scenes": [],
                "lights": [],
            },
        },
        "lights": {
            "1": {
                "ctmax": 454,
                "ctmin": 155,
                "name": "Tunable white light",
                "state": {"on": True, "colormode": "ct", "ct": 2500, "reachable": True},
                "type": "Tunable white light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(
            hass,
            aioclient_mock,
            options={CONF_ALLOW_DECONZ_GROUPS: False},
        )

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("light.tunable_white_light")
    assert not hass.states.get("light.light_group")
    assert not hass.states.get("light.empty_group")

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_DECONZ_GROUPS: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("light.light_group")

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_DECONZ_GROUPS: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert not hass.states.get("light.light_group")


async def test_non_color_light_reports_color(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_deconz_websocket
) -> None:
    """Verify hs_color does not crash when a group gets updated with a bad color value.

    After calling a scene color temp light of certain manufacturers
    report color temp in color space.
    """
    data = {
        "groups": {
            "0": {
                "action": {
                    "alert": "none",
                    "bri": 127,
                    "colormode": "hs",
                    "ct": 0,
                    "effect": "none",
                    "hue": 0,
                    "on": True,
                    "sat": 127,
                    "scene": None,
                    "xy": [0, 0],
                },
                "devicemembership": [],
                "etag": "81e42cf1b47affb72fa72bc2e25ba8bf",
                "lights": ["0", "1"],
                "name": "Group",
                "scenes": [],
                "state": {"all_on": False, "any_on": True},
                "type": "LightGroup",
            }
        },
        "lights": {
            "0": {
                "ctmax": 500,
                "ctmin": 153,
                "etag": "026bcfe544ad76c7534e5ca8ed39047c",
                "hascolor": True,
                "manufacturername": "dresden elektronik",
                "modelid": "FLS-PP3",
                "name": "Light 1",
                "pointsymbol": {},
                "state": {
                    "alert": None,
                    "bri": 111,
                    "colormode": "ct",
                    "ct": 307,
                    "effect": None,
                    "hascolor": True,
                    "hue": 7998,
                    "on": False,
                    "reachable": True,
                    "sat": 172,
                    "xy": [0.421253, 0.39921],
                },
                "swversion": "020C.201000A0",
                "type": "Extended color light",
                "uniqueid": "00:21:2E:FF:FF:EE:DD:CC-0A",
            },
            "1": {
                "colorcapabilities": 0,
                "ctmax": 65535,
                "ctmin": 0,
                "etag": "9dd510cd474791481f189d2a68a3c7f1",
                "hascolor": True,
                "lastannounced": "2020-12-17T17:44:38Z",
                "lastseen": "2021-01-11T18:36Z",
                "manufacturername": "IKEA of Sweden",
                "modelid": "TRADFRI bulb E27 WS opal 1000lm",
                "name": "Küchenlicht",
                "state": {
                    "alert": "none",
                    "bri": 156,
                    "colormode": "ct",
                    "ct": 250,
                    "on": True,
                    "reachable": True,
                },
                "swversion": "2.0.022",
                "type": "Color temperature light",
                "uniqueid": "ec:1b:bd:ff:fe:ee:ed:dd-01",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("light.group").attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.XY,
    ]
    assert (
        hass.states.get("light.group").attributes[ATTR_COLOR_MODE]
        == ColorMode.COLOR_TEMP
    )
    assert hass.states.get("light.group").attributes[ATTR_COLOR_TEMP] == 250

    # Updating a scene will return a faulty color value
    # for a non-color light causing an exception in hs_color
    event_changed_light = {
        "e": "changed",
        "id": "1",
        "r": "lights",
        "state": {
            "alert": None,
            "bri": 216,
            "colormode": "xy",
            "ct": 410,
            "on": True,
            "reachable": True,
        },
        "t": "event",
        "uniqueid": "ec:1b:bd:ff:fe:ee:ed:dd-01",
    }
    await mock_deconz_websocket(data=event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("light.group").attributes[ATTR_COLOR_MODE] == ColorMode.XY
    # Bug is fixed if we reach this point
    # device won't have neither color temp nor color
    with pytest.raises(AssertionError):
        assert hass.states.get("light.group").attributes.get(ATTR_COLOR_TEMP) is None
        assert hass.states.get("light.group").attributes.get(ATTR_HS_COLOR) is None


async def test_verify_group_supported_features(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that group supported features reflect what included lights support."""
    data = {
        "groups": {
            "1": {
                "id": "Group1",
                "name": "Group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {},
                "scenes": [],
                "lights": ["1", "2", "3"],
            },
        },
        "lights": {
            "1": {
                "name": "Dimmable light",
                "state": {"on": True, "bri": 255, "reachable": True},
                "type": "Light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "2": {
                "name": "Color light",
                "state": {
                    "on": True,
                    "bri": 100,
                    "colormode": "xy",
                    "effect": "colorloop",
                    "xy": (500, 500),
                    "reachable": True,
                },
                "type": "Extended color light",
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
            "3": {
                "ctmax": 454,
                "ctmin": 155,
                "name": "Tunable light",
                "state": {"on": True, "colormode": "ct", "ct": 2500, "reachable": True},
                "type": "Tunable white light",
                "uniqueid": "00:00:00:00:00:00:00:03-00",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 4

    assert hass.states.get("light.group").state == STATE_ON
    assert (
        hass.states.get("light.group").attributes[ATTR_SUPPORTED_FEATURES]
        == LightEntityFeature.TRANSITION
        | LightEntityFeature.FLASH
        | LightEntityFeature.EFFECT
    )
