"""Test reproduce state for Input number."""
from homeassistant.core import State
from homeassistant.setup import async_setup_component


async def test_reproducing_states(hass, caplog):
    """Test reproducing Input number states."""

    assert await async_setup_component(
        hass,
        "input_number",
        {
            "input_number": {
                "testint": {"min": "0", "max": "100", "initial": "19"},
                "testfloat": {"min": "0", "max": "100", "initial": "19.0"},
            }
        },
    )

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("input_number.testint", "19"),
            State("input_number.testfloat", "5.77"),
            # Should not raise
            State("input_number.non_existing", "234"),
        ],
        blocking=True,
    )

    assert hass.states.get("input_number.testint").state == "19.0"
    assert hass.states.get("input_number.testfloat").state == "5.77"

    # Test reproducing with different state
    await hass.helpers.state.async_reproduce_state(
        [
            State("input_number.testint", "18"),
            State("input_number.testfloat", "7.55"),
            # Should not raise
            State("input_number.non_existing", "234"),
        ],
        blocking=True,
    )

    assert hass.states.get("input_number.testint").state == "18.0"
    assert hass.states.get("input_number.testfloat").state == "7.55"

    await hass.helpers.state.async_reproduce_state(
        [
            # Test invalid state
            State("input_number.testint", "invalid_state"),
            # Set to state it already is.
            State("input_number.testint", "18.0"),
        ],
        blocking=True,
    )
