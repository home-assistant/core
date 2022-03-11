"""Test reproduce state for Fan."""
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Fan states."""
    hass.states.async_set("fan.entity_off", "off", {})
    hass.states.async_set("fan.entity_on", "on", {})
    hass.states.async_set("fan.entity_speed", "on", {"percentage": 100})
    hass.states.async_set("fan.entity_oscillating", "on", {"oscillating": True})
    hass.states.async_set("fan.entity_direction", "on", {"direction": "forward"})

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_calls = async_mock_service(hass, "fan", "set_percentage")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("fan.entity_off", "off"),
            State("fan.entity_on", "on"),
            State("fan.entity_speed", "on", {"percentage": 100}),
            State("fan.entity_oscillating", "on", {"oscillating": True}),
            State("fan.entity_direction", "on", {"direction": "forward"}),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("fan.entity_off", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("fan.entity_on", "off"),
            State("fan.entity_off", "on"),
            State("fan.entity_speed", "on", {"percentage": 25}),
            State("fan.entity_oscillating", "on", {"oscillating": False}),
            State("fan.entity_direction", "on", {"direction": "reverse"}),
            # Should not raise
            State("fan.non_existing", "on"),
        ],
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {"entity_id": "fan.entity_off"}

    assert len(set_direction_calls) == 1
    assert set_direction_calls[0].domain == "fan"
    assert set_direction_calls[0].data == {
        "entity_id": "fan.entity_direction",
        "direction": "reverse",
    }

    assert len(oscillate_calls) == 1
    assert oscillate_calls[0].domain == "fan"
    assert oscillate_calls[0].data == {
        "entity_id": "fan.entity_oscillating",
        "oscillating": False,
    }

    assert len(set_percentage_calls) == 1
    assert set_percentage_calls[0].domain == "fan"
    assert set_percentage_calls[0].data == {
        "entity_id": "fan.entity_speed",
        "percentage": 25,
    }

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "fan"
    assert turn_off_calls[0].data == {"entity_id": "fan.entity_on"}
