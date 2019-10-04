"""Test reproduce state for Light."""
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Light states."""
    hass.states.async_set("light.entity_off", "off", {})
    hass.states.async_set("light.entity_bright", "on", {"brightness": 180})
    hass.states.async_set("light.entity_white", "on", {"white_value": 200})
    hass.states.async_set("light.entity_flash", "on", {"flash": "short"})
    hass.states.async_set("light.entity_effect", "on", {"effect": "random"})
    hass.states.async_set("light.entity_trans", "on", {"transition": 15})
    hass.states.async_set("light.entity_name", "on", {"color_name": "red"})
    hass.states.async_set("light.entity_temp", "on", {"color_temp": 240})
    hass.states.async_set("light.entity_hs", "on", {"hs_color": (345, 75)})
    hass.states.async_set("light.entity_kelvin", "on", {"kelvin": 4000})
    hass.states.async_set("light.entity_profile", "on", {"profile": "relax"})
    hass.states.async_set("light.entity_rgb", "on", {"rgb_color": (255, 63, 111)})
    hass.states.async_set("light.entity_xy", "on", {"xy_color": (0.59, 0.274)})

    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    turn_off_calls = async_mock_service(hass, "light", "turn_off")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("light.entity_off", "off"),
            State("light.entity_bright", "on", {"brightness": 180}),
            State("light.entity_white", "on", {"white_value": 200}),
            State("light.entity_flash", "on", {"flash": "short"}),
            State("light.entity_effect", "on", {"effect": "random"}),
            State("light.entity_trans", "on", {"transition": 15}),
            State("light.entity_name", "on", {"color_name": "red"}),
            State("light.entity_temp", "on", {"color_temp": 240}),
            State("light.entity_hs", "on", {"hs_color": (345, 75)}),
            State("light.entity_kelvin", "on", {"kelvin": 4000}),
            State("light.entity_profile", "on", {"profile": "relax"}),
            State("light.entity_rgb", "on", {"rgb_color": (255, 63, 111)}),
            State("light.entity_xy", "on", {"xy_color": (0.59, 0.274)}),
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
            State("light.entity_off", "on", {"brightness": 180}),
            State("light.entity_bright", "on", {"white_value": 200}),
            State("light.entity_white", "on", {"flash": "short"}),
            State("light.entity_flash", "on", {"effect": "random"}),
            State("light.entity_effect", "on", {"transition": 15}),
            State("light.entity_trans", "on", {"color_name": "red"}),
            State("light.entity_name", "on", {"color_temp": 240}),
            State("light.entity_temp", "on", {"hs_color": (345, 75)}),
            State("light.entity_hs", "on", {"kelvin": 4000}),
            State("light.entity_kelvin", "on", {"profile": "relax"}),
            State("light.entity_profile", "on", {"rgb_color": (255, 63, 111)}),
            State("light.entity_rgb", "on", {"xy_color": (0.59, 0.274)}),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 12

    for i in range(0, 12):
        assert turn_on_calls[i].domain == "light"

    assert turn_on_calls[0].data == {"entity_id": "light.entity_off", "brightness": 180}
    assert turn_on_calls[1].data == {
        "entity_id": "light.entity_bright",
        "white_value": 200,
    }
    assert turn_on_calls[2].data == {
        "entity_id": "light.entity_white",
        "flash": "short",
    }
    assert turn_on_calls[3].data == {
        "entity_id": "light.entity_flash",
        "effect": "random",
    }
    assert turn_on_calls[4].data == {
        "entity_id": "light.entity_effect",
        "transition": 15,
    }
    assert turn_on_calls[5].data == {
        "entity_id": "light.entity_trans",
        "color_name": "red",
    }
    assert turn_on_calls[6].data == {
        "entity_id": "light.entity_name",
        "color_temp": 240,
    }
    assert turn_on_calls[7].data == {
        "entity_id": "light.entity_temp",
        "hs_color": (345, 75),
    }
    assert turn_on_calls[8].data == {"entity_id": "light.entity_hs", "kelvin": 4000}
    assert turn_on_calls[9].data == {
        "entity_id": "light.entity_kelvin",
        "profile": "relax",
    }
    assert turn_on_calls[10].data == {
        "entity_id": "light.entity_profile",
        "rgb_color": (255, 63, 111),
    }
    assert turn_on_calls[11].data == {
        "entity_id": "light.entity_rgb",
        "xy_color": (0.59, 0.274),
    }

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "light"
    assert turn_off_calls[0].data == {"entity_id": "light.entity_xy"}
