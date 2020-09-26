"""Test reproduce state for Counter."""
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Counter states."""
    hass.states.async_set("counter.entity", "5", {})
    hass.states.async_set(
        "counter.entity_attr",
        "8",
        {"initial": 12, "minimum": 5, "maximum": 15, "step": 3},
    )

    configure_calls = async_mock_service(hass, "counter", "configure")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("counter.entity", "5"),
            State(
                "counter.entity_attr",
                "8",
                {"initial": 12, "minimum": 5, "maximum": 15, "step": 3},
            ),
        ]
    )

    assert len(configure_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("counter.entity", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(configure_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("counter.entity", "2"),
            State(
                "counter.entity_attr",
                "7",
                {"initial": 10, "minimum": 3, "maximum": 21, "step": 5},
            ),
            # Should not raise
            State("counter.non_existing", "6"),
        ]
    )

    valid_calls = [
        {"entity_id": "counter.entity", "value": "2"},
        {
            "entity_id": "counter.entity_attr",
            "value": "7",
            "initial": 10,
            "minimum": 3,
            "maximum": 21,
            "step": 5,
        },
    ]
    assert len(configure_calls) == 2
    for call in configure_calls:
        assert call.domain == "counter"
        assert call.data in valid_calls
        valid_calls.remove(call.data)
