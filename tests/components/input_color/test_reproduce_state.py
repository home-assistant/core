"""Test reproduce state for Input Color."""

import pytest

from homeassistant.components.input_color import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_KIND,
    DOMAIN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.setup import async_setup_component


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Input Color states."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_color": {"initial_color": "#FF0000"}}},
    )

    await async_reproduce_state(
        hass,
        [
            State("input_color.test_color", "#FF0000"),
            State("input_color.non_existing", "#00FF00"),
        ],
    )
    assert hass.states.get("input_color.test_color").state == "#FF0000"

    await async_reproduce_state(
        hass,
        [
            State(
                "input_color.test_color",
                "#00FF00",
                {
                    ATTR_HEX_COLOR: "#00FF00",
                    ATTR_KIND: "chromatic",
                    ATTR_BRIGHTNESS: 150,
                },
            )
        ],
    )
    state = hass.states.get("input_color.test_color")
    assert state.state == "#00FF00"
    assert state.attributes[ATTR_BRIGHTNESS] == 150

    await async_reproduce_state(
        hass,
        [
            State(
                "input_color.test_color",
                "#FFD7B5",
                {
                    ATTR_COLOR_TEMP_KELVIN: 2700,
                    ATTR_BRIGHTNESS: None,
                },
            )
        ],
    )
    state = hass.states.get("input_color.test_color")
    assert state.attributes[ATTR_KIND] == "white"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_BRIGHTNESS] is None
