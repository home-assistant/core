"""Test reproduce state for input boolean."""
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.setup import async_setup_component


async def test_reproducing_states(hass: HomeAssistant) -> None:
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
    await async_reproduce_state(
        hass,
        [
            State("input_boolean.initial_on", "off"),
            State("input_boolean.initial_off", "on"),
            # Should not raise
            State("input_boolean.non_existing", "on"),
        ],
    )
    assert hass.states.get("input_boolean.initial_off").state == "on"
    assert hass.states.get("input_boolean.initial_on").state == "off"

    await async_reproduce_state(
        hass,
        [
            # Test invalid state
            State("input_boolean.initial_on", "invalid_state"),
            # Set to state it already is.
            State("input_boolean.initial_off", "on"),
        ],
    )

    assert hass.states.get("input_boolean.initial_on").state == "off"
    assert hass.states.get("input_boolean.initial_off").state == "on"
