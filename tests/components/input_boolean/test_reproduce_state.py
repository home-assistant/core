"""Test reproduce state for input boolean."""
from homeassistant.core import State
from homeassistant.setup import async_setup_component


async def test_reproducing_states(hass):
    """Test reproducing input_boolean states."""
    assert await async_setup_component(
        hass,
        "input_boolean",
        {
            "input_boolean": {
                "initial_on": {"initial": True},
                "initial_off": {"initial": False},
            }
        },
    )
    await hass.helpers.state.async_reproduce_state(
        [
            State("input_boolean.initial_on", "off"),
            State("input_boolean.initial_off", "on"),
            # Should not raise
            State("input_boolean.non_existing", "on"),
        ],
    )
    assert hass.states.get("input_boolean.initial_off").state == "on"
    assert hass.states.get("input_boolean.initial_on").state == "off"

    await hass.helpers.state.async_reproduce_state(
        [
            # Test invalid state
            State("input_boolean.initial_on", "invalid_state"),
            # Set to state it already is.
            State("input_boolean.initial_off", "on"),
        ],
    )

    assert hass.states.get("input_boolean.initial_on").state == "off"
    assert hass.states.get("input_boolean.initial_off").state == "on"
