"""Test reproduce state for Switch."""
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Switch states."""
    hass.states.async_set("switch.entity_off", "off", {})
    hass.states.async_set("switch.entity_on", "on", {})

    turn_on_calls = async_mock_service(hass, "switch", "turn_on")
    turn_off_calls = async_mock_service(hass, "switch", "turn_off")

    # Even if the target state is the same as the current we still needs
    # to do the calls, as the current state is just a cache of the real one
    # and could be not up to date.
    await hass.helpers.state.async_reproduce_state(
        [State("switch.entity_off", "off"), State("switch.entity_on", "on", {})],
        blocking=True,
    )

    assert len(turn_on_calls) == 1
    assert len(turn_off_calls) == 1

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("switch.entity_off", "not_supported")], blocking=True
    )

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 1
    assert len(turn_off_calls) == 1

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("switch.entity_on", "off"),
            State("switch.entity_off", "on", {}),
            # Should not raise
            State("switch.non_existing", "on"),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 2
    assert turn_on_calls[1].domain == "switch"
    assert turn_on_calls[1].data == {"entity_id": "switch.entity_off"}

    assert len(turn_off_calls) == 2
    assert turn_off_calls[1].domain == "switch"
    assert turn_off_calls[1].data == {"entity_id": "switch.entity_on"}
