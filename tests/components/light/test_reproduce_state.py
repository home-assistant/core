"""Test reproduce state for Light."""
from homeassistant.core import State

from tests.common import async_mock_service

VALID_BRIGHTNESS = {"brightness": 180}
VALID_WHITE_VALUE = {"white_value": 200}
VALID_EFFECT = {"effect": "random"}
VALID_COLOR_TEMP = {"color_temp": 240}
VALID_HS_COLOR = {"hs_color": (345, 75)}
VALID_RGB_COLOR = {"rgb_color": (255, 63, 111)}
VALID_XY_COLOR = {"xy_color": (0.59, 0.274)}


async def test_reproducing_states(hass, caplog):
    """Test reproducing Light states."""
    hass.states.async_set("light.entity_off", "off", {})
    hass.states.async_set("light.entity_bright", "on", VALID_BRIGHTNESS)
    hass.states.async_set("light.entity_white", "on", VALID_WHITE_VALUE)
    hass.states.async_set("light.entity_effect", "on", VALID_EFFECT)
    hass.states.async_set("light.entity_temp", "on", VALID_COLOR_TEMP)
    hass.states.async_set("light.entity_hs", "on", VALID_HS_COLOR)
    hass.states.async_set("light.entity_rgb", "on", VALID_RGB_COLOR)
    hass.states.async_set("light.entity_xy", "on", VALID_XY_COLOR)

    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    turn_off_calls = async_mock_service(hass, "light", "turn_off")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("light.entity_off", "off"),
            State("light.entity_bright", "on", VALID_BRIGHTNESS),
            State("light.entity_white", "on", VALID_WHITE_VALUE),
            State("light.entity_effect", "on", VALID_EFFECT),
            State("light.entity_temp", "on", VALID_COLOR_TEMP),
            State("light.entity_hs", "on", VALID_HS_COLOR),
            State("light.entity_rgb", "on", VALID_RGB_COLOR),
            State("light.entity_xy", "on", VALID_XY_COLOR),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("light.entity_off", "not_supported")], blocking=True
    )

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("light.entity_xy", "off"),
            State("light.entity_off", "on", VALID_BRIGHTNESS),
            State("light.entity_bright", "on", VALID_WHITE_VALUE),
            State("light.entity_white", "on", VALID_EFFECT),
            State("light.entity_effect", "on", VALID_COLOR_TEMP),
            State("light.entity_temp", "on", VALID_HS_COLOR),
            State("light.entity_hs", "on", VALID_RGB_COLOR),
            State("light.entity_rgb", "on", VALID_XY_COLOR),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 7

    expected_calls = []

    expected_off = VALID_BRIGHTNESS
    expected_off["entity_id"] = "light.entity_off"
    expected_calls.append(expected_off)

    expected_bright = VALID_WHITE_VALUE
    expected_bright["entity_id"] = "light.entity_bright"
    expected_calls.append(expected_bright)

    expected_white = VALID_EFFECT
    expected_white["entity_id"] = "light.entity_white"
    expected_calls.append(expected_white)

    expected_effect = VALID_COLOR_TEMP
    expected_effect["entity_id"] = "light.entity_effect"
    expected_calls.append(expected_effect)

    expected_temp = VALID_HS_COLOR
    expected_temp["entity_id"] = "light.entity_temp"
    expected_calls.append(expected_temp)

    expected_hs = VALID_RGB_COLOR
    expected_hs["entity_id"] = "light.entity_hs"
    expected_calls.append(expected_hs)

    expected_rgb = VALID_XY_COLOR
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
