"""Test reproduce state for Input select."""
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from tests.common import async_mock_service

VALID_OPTION1 = "Option A"
VALID_OPTION2 = "Option B"
VALID_OPTION3 = "Option C"
VALID_OPTION4 = "Option D"
VALID_OPTION5 = "Option E"
VALID_OPTION6 = "Option F"
INVALID_OPTION = "Option X"
VALID_OPTION_SET1 = [VALID_OPTION1, VALID_OPTION2, VALID_OPTION3]
VALID_OPTION_SET2 = [VALID_OPTION4, VALID_OPTION5, VALID_OPTION6]
ENTITY = "input_select.test_select"


async def test_reproducing_states(hass, caplog):
    """Test reproducing Input select states."""

    # Setup entity
    assert await async_setup_component(
        hass,
        "input_select",
        {
            "input_select": {
                "test_select": {"options": VALID_OPTION_SET1, "initial": VALID_OPTION1}
            }
        },
    )

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State(ENTITY, VALID_OPTION1),
            # Should not raise
            State("input_select.non_existing", VALID_OPTION1),
        ],
        blocking=True,
    )

    # Test that entity is in desired state
    assert hass.states.get(ENTITY).state == VALID_OPTION1

    # Try reproducing with different state
    await hass.helpers.state.async_reproduce_state(
        [
            State(ENTITY, VALID_OPTION3),
            # Should not raise
            State("input_select.non_existing", VALID_OPTION3),
        ],
        blocking=True,
    )

    # Test that we got the desired result
    assert hass.states.get(ENTITY).state == VALID_OPTION3

    # Test setting state to invalid state
    await hass.helpers.state.async_reproduce_state(
        [State(ENTITY, INVALID_OPTION)], blocking=True
    )

    # The entity state should be unchanged
    assert hass.states.get(ENTITY).state == VALID_OPTION3

    # Test setting a different set of options
    set_options_calls = async_mock_service(hass, "input_select", "set_options")
    select_option_calls = async_mock_service(hass, "input_select", "select_option")

    await hass.helpers.state.async_reproduce_state(
        [State(ENTITY, VALID_OPTION5, {"options": VALID_OPTION_SET2})], blocking=True
    )

    # Test that both set_options and select_option were called
    assert len(select_option_calls) == 1
    assert select_option_calls[0].data == {"entity_id": ENTITY, "option": VALID_OPTION5}

    assert len(set_options_calls) == 1
    assert set_options_calls[0].data == {"entity_id": ENTITY, "option": VALID_OPTION5}
