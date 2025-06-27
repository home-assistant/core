"""Test reproduce state for Light."""

import pytest

from homeassistant.components import light
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service

VALID_BRIGHTNESS = {"brightness": 180}
VALID_EFFECT = {"effect": "random"}
VALID_COLOR_TEMP_KELVIN = {"color_temp_kelvin": 4200}
VALID_HS_COLOR = {"hs_color": (345, 75)}
VALID_RGB_COLOR = {"rgb_color": (255, 63, 111)}
VALID_RGBW_COLOR = {"rgbw_color": (255, 63, 111, 10)}
VALID_RGBWW_COLOR = {"rgbww_color": (255, 63, 111, 10, 20)}
VALID_XY_COLOR = {"xy_color": (0.59, 0.274)}

NONE_BRIGHTNESS = {"brightness": None}
NONE_EFFECT = {"effect": None}
NONE_COLOR_TEMP_KELVIN = {"color_temp_kelvin": None}
NONE_HS_COLOR = {"hs_color": None}
NONE_RGB_COLOR = {"rgb_color": None}
NONE_RGBW_COLOR = {"rgbw_color": None}
NONE_RGBWW_COLOR = {"rgbww_color": None}
NONE_XY_COLOR = {"xy_color": None}


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Light states."""
    hass.states.async_set("light.entity_off", "off", {})
    hass.states.async_set("light.entity_bright", "on", VALID_BRIGHTNESS)
    hass.states.async_set("light.entity_effect", "on", VALID_EFFECT)
    hass.states.async_set("light.entity_temp", "on", VALID_COLOR_TEMP_KELVIN)
    hass.states.async_set("light.entity_hs", "on", VALID_HS_COLOR)
    hass.states.async_set("light.entity_rgb", "on", VALID_RGB_COLOR)
    hass.states.async_set("light.entity_xy", "on", VALID_XY_COLOR)

    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    turn_off_calls = async_mock_service(hass, "light", "turn_off")

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("light.entity_off", "off"),
            State("light.entity_bright", "on", VALID_BRIGHTNESS),
            State("light.entity_effect", "on", VALID_EFFECT),
            State("light.entity_temp", "on", VALID_COLOR_TEMP_KELVIN),
            State("light.entity_hs", "on", VALID_HS_COLOR),
            State("light.entity_rgb", "on", VALID_RGB_COLOR),
            State("light.entity_xy", "on", VALID_XY_COLOR),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("light.entity_off", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("light.entity_xy", "off"),
            State("light.entity_off", "on", VALID_BRIGHTNESS),
            State("light.entity_bright", "on", VALID_EFFECT),
            State("light.entity_effect", "on", VALID_COLOR_TEMP_KELVIN),
            State("light.entity_temp", "on", VALID_HS_COLOR),
            State("light.entity_hs", "on", VALID_RGB_COLOR),
            State("light.entity_rgb", "on", VALID_XY_COLOR),
        ],
    )

    assert len(turn_on_calls) == 6

    expected_calls = []

    expected_off = dict(VALID_BRIGHTNESS)
    expected_off["entity_id"] = "light.entity_off"
    expected_calls.append(expected_off)

    expected_bright = dict(VALID_EFFECT)
    expected_bright["entity_id"] = "light.entity_bright"
    expected_calls.append(expected_bright)

    expected_effect = dict(VALID_COLOR_TEMP_KELVIN)
    expected_effect["entity_id"] = "light.entity_effect"
    expected_calls.append(expected_effect)

    expected_temp = dict(VALID_HS_COLOR)
    expected_temp["entity_id"] = "light.entity_temp"
    expected_calls.append(expected_temp)

    expected_hs = dict(VALID_RGB_COLOR)
    expected_hs["entity_id"] = "light.entity_hs"
    expected_calls.append(expected_hs)

    expected_rgb = dict(VALID_XY_COLOR)
    expected_rgb["entity_id"] = "light.entity_rgb"
    expected_calls.append(expected_rgb)

    for call in turn_on_calls:
        assert call.domain == "light"
        found = False
        for expected in expected_calls:
            if call.data["entity_id"] == expected["entity_id"]:
                # We found the matching entry
                assert call.data == expected
                found = True
                break
        # No entry found
        assert found

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "light"
    assert turn_off_calls[0].data == {"entity_id": "light.entity_xy"}


@pytest.mark.parametrize(
    "color_mode",
    [
        light.ColorMode.COLOR_TEMP,
        light.ColorMode.BRIGHTNESS,
        light.ColorMode.HS,
        light.ColorMode.ONOFF,
        light.ColorMode.RGB,
        light.ColorMode.RGBW,
        light.ColorMode.RGBWW,
        light.ColorMode.UNKNOWN,
        light.ColorMode.WHITE,
        light.ColorMode.XY,
    ],
)
async def test_filter_color_modes(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, color_mode
) -> None:
    """Test filtering of parameters according to color mode."""
    hass.states.async_set("light.entity", "off", {})
    all_colors = {
        **VALID_COLOR_TEMP_KELVIN,
        **VALID_HS_COLOR,
        **VALID_RGB_COLOR,
        **VALID_RGBW_COLOR,
        **VALID_RGBWW_COLOR,
        **VALID_XY_COLOR,
        **VALID_BRIGHTNESS,
    }

    turn_on_calls = async_mock_service(hass, "light", "turn_on")

    await async_reproduce_state(
        hass, [State("light.entity", "on", {**all_colors, "color_mode": color_mode})]
    )

    expected_map = {
        light.ColorMode.COLOR_TEMP: {**VALID_BRIGHTNESS, **VALID_COLOR_TEMP_KELVIN},
        light.ColorMode.BRIGHTNESS: VALID_BRIGHTNESS,
        light.ColorMode.HS: {**VALID_BRIGHTNESS, **VALID_HS_COLOR},
        light.ColorMode.ONOFF: {**VALID_BRIGHTNESS},
        light.ColorMode.RGB: {**VALID_BRIGHTNESS, **VALID_RGB_COLOR},
        light.ColorMode.RGBW: {**VALID_BRIGHTNESS, **VALID_RGBW_COLOR},
        light.ColorMode.RGBWW: {**VALID_BRIGHTNESS, **VALID_RGBWW_COLOR},
        light.ColorMode.UNKNOWN: {
            **VALID_BRIGHTNESS,
            **VALID_HS_COLOR,
        },
        light.ColorMode.WHITE: {
            **VALID_BRIGHTNESS,
            light.ATTR_WHITE: VALID_BRIGHTNESS[light.ATTR_BRIGHTNESS],
        },
        light.ColorMode.XY: {**VALID_BRIGHTNESS, **VALID_XY_COLOR},
    }
    expected = expected_map[color_mode]

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "light"
    assert dict(turn_on_calls[0].data) == {"entity_id": "light.entity", **expected}

    # This should do nothing, the light is already in the desired state
    hass.states.async_set("light.entity", "on", {"color_mode": color_mode, **expected})
    await async_reproduce_state(
        hass, [State("light.entity", "on", {**expected, "color_mode": color_mode})]
    )
    assert len(turn_on_calls) == 1


async def test_filter_color_modes_missing_attributes(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test warning on missing attribute when filtering for color mode."""
    color_mode = light.ColorMode.COLOR_TEMP
    hass.states.async_set("light.entity", "off", {})
    expected_log = (
        "Color mode color_temp specified "
        "but attribute color_temp_kelvin missing for: light.entity"
    )
    expected_fallback_log = "using color_temp (mireds) as fallback"

    turn_on_calls = async_mock_service(hass, "light", "turn_on")

    all_colors = {
        **VALID_COLOR_TEMP_KELVIN,
        **VALID_HS_COLOR,
        **VALID_RGB_COLOR,
        **VALID_RGBW_COLOR,
        **VALID_RGBWW_COLOR,
        **VALID_XY_COLOR,
        **VALID_BRIGHTNESS,
    }

    # Test missing `color_temp_kelvin` attribute
    stored_attributes = {**all_colors}
    stored_attributes.pop("color_temp_kelvin")
    caplog.clear()
    await async_reproduce_state(
        hass,
        [State("light.entity", "on", {**stored_attributes, "color_mode": color_mode})],
    )
    assert len(turn_on_calls) == 0
    assert expected_log in caplog.text
    assert expected_fallback_log not in caplog.text

    # Test with deprecated `color_temp` attribute
    stored_attributes["color_temp"] = 250
    expected = {"brightness": 180, "color_temp_kelvin": 4000}
    caplog.clear()
    await async_reproduce_state(
        hass,
        [State("light.entity", "on", {**stored_attributes, "color_mode": color_mode})],
    )

    assert len(turn_on_calls) == 1
    assert expected_log in caplog.text
    assert expected_fallback_log in caplog.text

    # Test with correct `color_temp_kelvin` attribute
    expected = {"brightness": 180, "color_temp_kelvin": 4200}
    caplog.clear()
    turn_on_calls.clear()
    await async_reproduce_state(
        hass,
        [State("light.entity", "on", {**all_colors, "color_mode": color_mode})],
    )
    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "light"
    assert dict(turn_on_calls[0].data) == {"entity_id": "light.entity", **expected}
    assert expected_log not in caplog.text
    assert expected_fallback_log not in caplog.text


@pytest.mark.parametrize(
    "saved_state",
    [
        NONE_BRIGHTNESS,
        NONE_EFFECT,
        NONE_COLOR_TEMP_KELVIN,
        NONE_HS_COLOR,
        NONE_RGB_COLOR,
        NONE_RGBW_COLOR,
        NONE_RGBWW_COLOR,
        NONE_XY_COLOR,
    ],
)
async def test_filter_none(hass: HomeAssistant, saved_state) -> None:
    """Test filtering of parameters which are None."""
    hass.states.async_set("light.entity", "off", {})

    turn_on_calls = async_mock_service(hass, "light", "turn_on")

    await async_reproduce_state(hass, [State("light.entity", "on", saved_state)])

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "light"
    assert dict(turn_on_calls[0].data) == {"entity_id": "light.entity"}

    # This should do nothing, the light is already in the desired state
    hass.states.async_set("light.entity", "on", {})
    await async_reproduce_state(hass, [State("light.entity", "on", saved_state)])
    assert len(turn_on_calls) == 1
