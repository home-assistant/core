"""deCONZ light platform tests."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.deconz.const import CONF_ALLOW_DECONZ_GROUPS
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
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
            }
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
            }
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
            }
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
            }
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
            }
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
            }
        ),
        (  # Gradient light
            {
                "capabilities": {
                    "alerts": [
                        "none",
                        "select",
                        "lselect",
                        "blink",
                        "breathe",
                        "okay",
                        "channelchange",
                        "finish",
                        "stop",
                    ],
                    "bri": {"min_dim_level": 0.01},
                    "color": {
                        "ct": {"computes_xy": True, "max": 500, "min": 153},
                        "effects": [
                            "none",
                            "colorloop",
                            "candle",
                            "fireplace",
                            "prism",
                            "sunrise",
                        ],
                        "gamut_type": "C",
                        "gradient": {
                            "max_segments": 9,
                            "pixel_count": 16,
                            "pixel_length": 1250,
                            "styles": ["linear", "mirrored"],
                        },
                        "modes": ["ct", "effect", "gradient", "hs", "xy"],
                        "xy": {
                            "blue": [0.1532, 0.0475],
                            "green": [0.17, 0.7],
                            "red": [0.6915, 0.3083],
                        },
                    },
                },
                "colorcapabilities": 31,
                "config": {
                    "bri": {
                        "couple_ct": False,
                        "execute_if_off": True,
                        "startup": "previous",
                    },
                    "color": {
                        "ct": {"startup": "previous"},
                        "execute_if_off": True,
                        "gradient": {"reversed": False},
                        "xy": {"startup": "previous"},
                    },
                    "groups": ["36", "39", "45", "46", "47", "51", "57", "59"],
                    "on": {"startup": "previous"},
                },
                "ctmax": 500,
                "ctmin": 153,
                "etag": "077fb97dd6145f10a3c190f0a1ade499",
                "hascolor": True,
                "lastannounced": None,
                "lastseen": "2024-02-29T18:36Z",
                "manufacturername": "Signify Netherlands B.V.",
                "modelid": "LCX004",
                "name": "Gradient light",
                "productid": "Philips-LCX004-1-GALSECLv1",
                "productname": "Hue gradient lightstrip",
                "state": {
                    "alert": "none",
                    "bri": 184,
                    "colormode": "gradient",
                    "ct": 396,
                    "effect": "none",
                    "gradient": {
                        "color_adjustment": 0,
                        "offset": 0,
                        "offset_adjustment": 0,
                        "points": [
                            [0.2728, 0.6226],
                            [0.163, 0.4262],
                            [0.1563, 0.1699],
                            [0.1551, 0.1147],
                            [0.1534, 0.0579],
                        ],
                        "segments": 5,
                        "style": "linear",
                    },
                    "hue": 20566,
                    "on": True,
                    "reachable": True,
                    "sat": 254,
                    "xy": [0.2727, 0.6226],
                },
                "swconfigid": "F03CAF4D",
                "swversion": "1.104.2",
                "type": "Extended color light",
                "uniqueid": "00:17:88:01:0b:0c:0d:0e-0f",
            }
        ),
    ],
)
async def test_lights(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that different light entities are created with expected values."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.LIGHT]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "light_payload",
    [
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
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_light_state_change(
    hass: HomeAssistant,
    light_ws_data: WebsocketDataType,
) -> None:
    """Verify light can change state on websocket event."""
    assert hass.states.get("light.hue_go").state == STATE_ON

    await light_ws_data({"state": {"on": False}})
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
                    ATTR_COLOR_TEMP_KELVIN: 5000,
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
                    ATTR_EFFECT: "none",
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
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    light_payload: dict[str, Any],
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    input: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Verify light can change state on websocket event."""
    light_payload[0] = {
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
    await config_entry_factory()

    aioclient_mock = mock_put_request("/lights/0/state")

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


@pytest.mark.parametrize(
    "light_payload",
    [
        {
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
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_ikea_default_transition_time(
    hass: HomeAssistant,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
) -> None:
    """Verify that service calls to IKEA lights always extend with transition tinme 0 if absent."""
    aioclient_mock = mock_put_request("/lights/0/state")

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


@pytest.mark.parametrize(
    "light_payload",
    [
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
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_lidl_christmas_light(
    hass: HomeAssistant,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
) -> None:
    """Test that lights or groups entities are created."""
    aioclient_mock = mock_put_request("/lights/0/state")

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


@pytest.mark.parametrize(
    "light_payload",
    [
        {
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
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_configuration_tool(hass: HomeAssistant) -> None:
    """Verify that configuration tool is not created."""
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "light_payload",
    [
        {
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
        }
    ],
)
@pytest.mark.parametrize(
    "input",
    [
        ({"lights": ["1", "2", "3"]}),
        ({"lights": ["3", "1", "2"]}),
        ({"lights": ["2", "3", "1"]}),
    ],
)
async def test_groups(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    group_payload: dict[str, Any],
    input: dict[str, list[str]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test that different group entities are created with expected values."""
    group_payload |= {
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
    }

    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.LIGHT]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "light_payload",
    [
        {
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
        }
    ],
)
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
                    ATTR_COLOR_TEMP_KELVIN: 5000,
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
                "xy": (0.236, 0.166),
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
                "xy": (0.236, 0.166),
            },
        ),
    ],
)
async def test_group_service_calls(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    group_payload: dict[str, Any],
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    input: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Verify expected group web request from different service calls."""
    group_payload |= {
        "0": {
            "id": "Light group id",
            "name": "Group",
            "type": "LightGroup",
            "state": {"all_on": False, "any_on": input["group_on"]},
            "action": {},
            "scenes": [],
            "lights": input["lights"],
        },
    }
    await config_entry_factory()

    aioclient_mock = mock_put_request("/groups/0/action")

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


@pytest.mark.parametrize(
    "group_payload",
    [
        {
            "0": {
                "id": "Empty group id",
                "name": "Empty group",
                "type": "LightGroup",
                "state": {},
                "action": {},
                "scenes": [],
                "lights": [],
            },
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_empty_group(hass: HomeAssistant) -> None:
    """Verify that a group without a list of lights is not created."""
    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("light.empty_group")


@pytest.mark.parametrize(
    "group_payload",
    [
        {
            "1": {
                "id": "Light group id",
                "name": "Light group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {},
                "scenes": [],
                "lights": ["0"],
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
        }
    ],
)
@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "ctmax": 454,
            "ctmin": 155,
            "name": "Tunable white light",
            "state": {"on": True, "colormode": "ct", "ct": 2500, "reachable": True},
            "type": "Tunable white light",
            "uniqueid": "00:00:00:00:00:00:00:01-00",
        }
    ],
)
@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_DECONZ_GROUPS: False}])
async def test_disable_light_groups(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test disallowing light groups work."""
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("light.tunable_white_light")
    assert not hass.states.get("light.light_group")
    assert not hass.states.get("light.empty_group")

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_DECONZ_GROUPS: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("light.light_group")

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_DECONZ_GROUPS: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert not hass.states.get("light.light_group")


@pytest.mark.parametrize(
    "group_payload",
    [
        {
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
        }
    ],
)
@pytest.mark.parametrize(
    "light_payload",
    [
        {
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
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_non_color_light_reports_color(
    hass: HomeAssistant,
    light_ws_data: WebsocketDataType,
) -> None:
    """Verify hs_color does not crash when a group gets updated with a bad color value.

    After calling a scene color temp light of certain manufacturers
    report color temp in color space.
    """
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
    assert hass.states.get("light.group").attributes[ATTR_COLOR_TEMP_KELVIN] == 4000

    # Updating a scene will return a faulty color value
    # for a non-color light causing an exception in hs_color
    event_changed_light = {
        "id": "1",
        "state": {
            "alert": None,
            "bri": 216,
            "colormode": "xy",
            "ct": 410,
            "on": True,
            "reachable": True,
        },
        "uniqueid": "ec:1b:bd:ff:fe:ee:ed:dd-01",
    }
    await light_ws_data(event_changed_light)
    group = hass.states.get("light.group")
    assert group.attributes[ATTR_COLOR_MODE] == ColorMode.XY
    assert group.attributes[ATTR_HS_COLOR] == (40.571, 41.176)
    assert group.attributes.get(ATTR_COLOR_TEMP_KELVIN) is None


@pytest.mark.parametrize(
    "group_payload",
    [
        {
            "1": {
                "id": "Group1",
                "name": "Group",
                "type": "LightGroup",
                "state": {"all_on": False, "any_on": True},
                "action": {},
                "scenes": [],
                "lights": ["1", "2", "3"],
            },
        }
    ],
)
@pytest.mark.parametrize(
    "light_payload",
    [
        {
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
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_verify_group_supported_features(hass: HomeAssistant) -> None:
    """Test that group supported features reflect what included lights support."""
    assert len(hass.states.async_all()) == 4

    group_state = hass.states.get("light.group")
    assert group_state.state == STATE_ON
    assert group_state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert (
        group_state.attributes[ATTR_SUPPORTED_FEATURES]
        == LightEntityFeature.TRANSITION
        | LightEntityFeature.FLASH
        | LightEntityFeature.EFFECT
    )


@pytest.mark.parametrize(
    "group_payload",
    [
        {
            "43": {
                "action": {
                    "alert": "none",
                    "bri": 127,
                    "colormode": "hs",
                    "ct": 0,
                    "effect": "none",
                    "hue": 0,
                    "on": True,
                    "sat": 127,
                    "scene": "4",
                    "xy": [0, 0],
                },
                "devicemembership": [],
                "etag": "4548e982c4cfff942f7af80958abb2a0",
                "id": "43",
                "lights": ["0"],
                "name": "Opbergruimte",
                "scenes": [
                    {
                        "id": "1",
                        "lightcount": 1,
                        "name": "Scene Normaal deCONZ",
                        "transitiontime": 10,
                    },
                    {
                        "id": "2",
                        "lightcount": 1,
                        "name": "Scene Fel deCONZ",
                        "transitiontime": 10,
                    },
                    {
                        "id": "3",
                        "lightcount": 1,
                        "name": "Scene Gedimd deCONZ",
                        "transitiontime": 10,
                    },
                    {
                        "id": "4",
                        "lightcount": 1,
                        "name": "Scene Uit deCONZ",
                        "transitiontime": 10,
                    },
                ],
                "state": {"all_on": False, "any_on": False},
                "type": "LightGroup",
            },
        }
    ],
)
@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "capabilities": {
                "alerts": [
                    "none",
                    "select",
                    "lselect",
                    "blink",
                    "breathe",
                    "okay",
                    "channelchange",
                    "finish",
                    "stop",
                ],
                "bri": {"min_dim_level": 5},
            },
            "config": {
                "bri": {"execute_if_off": True, "startup": "previous"},
                "groups": ["43"],
                "on": {"startup": "previous"},
            },
            "etag": "ca0ed7763eca37f5e6b24f6d46f8a518",
            "hascolor": False,
            "lastannounced": None,
            "lastseen": "2024-03-02T20:08Z",
            "manufacturername": "Signify Netherlands B.V.",
            "modelid": "LWA001",
            "name": "Opbergruimte Lamp Plafond",
            "productid": "Philips-LWA001-1-A19DLv5",
            "productname": "Hue white lamp",
            "state": {
                "alert": "none",
                "bri": 76,
                "effect": "none",
                "on": False,
                "reachable": True,
            },
            "swconfigid": "87169548",
            "swversion": "1.104.2",
            "type": "Dimmable light",
            "uniqueid": "00:17:88:01:08:11:22:33-01",
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_verify_group_color_mode_fallback(
    hass: HomeAssistant,
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that group supported features reflect what included lights support."""
    group_state = hass.states.get("light.opbergruimte")
    assert group_state.state == STATE_OFF
    assert group_state.attributes[ATTR_COLOR_MODE] is None

    await mock_websocket_data(
        {
            "id": "0",
            "r": "lights",
            "state": {
                "alert": "none",
                "bri": 76,
                "effect": "none",
                "on": True,
                "reachable": True,
            },
            "uniqueid": "00:17:88:01:08:11:22:33-01",
        }
    )
    await mock_websocket_data(
        {
            "id": "43",
            "r": "groups",
            "state": {"all_on": True, "any_on": True},
        }
    )
    group_state = hass.states.get("light.opbergruimte")
    assert group_state.state == STATE_ON
    assert group_state.attributes[ATTR_COLOR_MODE] is ColorMode.BRIGHTNESS
