"""Test reproduce state for Input text."""

import pytest

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.setup import async_setup_component

VALID_TEXT1 = "Test text"
VALID_TEXT2 = "LoremIpsum"
INVALID_TEXT1 = "This text is too long!"
INVALID_TEXT2 = "Short"


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Input text states."""

    # Setup entity for testing
    assert await async_setup_component(
        hass,
        "input_text",
        {
            "input_text": {
                "test_text": {"min": "6", "max": "10", "initial": VALID_TEXT1}
            }
        },
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("input_text.test_text", VALID_TEXT1),
            # Should not raise
            State("input_text.non_existing", VALID_TEXT1),
        ],
    )

    # Test that entity is in desired state
    assert hass.states.get("input_text.test_text").state == VALID_TEXT1

    # Try reproducing with different state
    await async_reproduce_state(
        hass,
        [
            State("input_text.test_text", VALID_TEXT2),
            # Should not raise
            State("input_text.non_existing", VALID_TEXT2),
        ],
    )

    # Test that the state was changed
    assert hass.states.get("input_text.test_text").state == VALID_TEXT2

    # Test setting state to invalid state (length too long)
    await async_reproduce_state(hass, [State("input_text.test_text", INVALID_TEXT1)])

    # The entity state should be unchanged
    assert hass.states.get("input_text.test_text").state == VALID_TEXT2

    # Test setting state to invalid state (length too short)
    await async_reproduce_state(hass, [State("input_text.test_text", INVALID_TEXT2)])

    # The entity state should be unchanged
    assert hass.states.get("input_text.test_text").state == VALID_TEXT2
