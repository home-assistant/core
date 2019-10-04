"""Test reproduce state for Light."""
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Light states."""
    hass.states.async_set("light.entity_off", "off", {})
    hass.states.async_set("light.entity_on", "on", {"color_name": "red"})

    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    turn_off_calls = async_mock_service(hass, "light", "turn_off")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("light.entity_off", "off"),
            State("light.entity_on", "on", {"color_name": "red"}),
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
            State("light.entity_on", "off"),
            State("light.entity_off", "on", {"color_name": "red"}),
            # Should not raise
            State("light.non_existing", "on"),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "light"
    assert turn_on_calls[0].data == {
        "entity_id": "light.entity_off",
        "color_name": "red",
    }

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "light"
    assert turn_off_calls[0].data == {"entity_id": "light.entity_on"}
