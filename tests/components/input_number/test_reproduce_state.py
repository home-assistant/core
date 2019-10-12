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
                "test_int": {"min": "5", "max": "100", "initial": "19"},
                "test_float": {"min": "5", "max": "100", "initial": "5.77"},
            }
        },
    )

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("input_number.test_int", "19"),
            State("input_number.test_float", "5.77"),
            # Should not raise
            State("input_number.non_existing", "234"),
        ],
        blocking=True,
    )

    assert hass.states.get("input_number.test_int").state == "19.0"
    assert hass.states.get("input_number.test_float").state == "5.77"

    # Test reproducing with different state
    await hass.helpers.state.async_reproduce_state(
        [
            State("input_number.test_int", "18"),
            State("input_number.test_float", "7.55"),
            # Should not raise
            State("input_number.non_existing", "234"),
        ],
        blocking=True,
    )

    assert hass.states.get("input_number.test_int").state == "18.0"
    assert hass.states.get("input_number.test_float").state == "7.55"

    # Test setting state to number out of range
    await hass.helpers.state.async_reproduce_state(
        [
            State("input_number.test_int", "150"),
            State("input_number.test_float", "1.23"),
        ],
        blocking=True,
    )

    # The entity states should be unchanged after trying to set them to out-of-range number
    assert hass.states.get("input_number.test_int").state == "18.0"
    assert hass.states.get("input_number.test_float").state == "7.55"

    await hass.helpers.state.async_reproduce_state(
        [
            # Test invalid state
            State("input_number.test_int", "invalid_state"),
            # Set to state it already is.
            State("input_number.test_int", "18.0"),
        ],
        blocking=True,
    )
