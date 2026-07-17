"""Test reproduce state for Counter."""

import pytest

from homeassistant.components.counter import DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Counter states."""
    hass.states.async_set("counter.entity", "5", {})
    hass.states.async_set(
        "counter.entity_attr", "8", {"minimum": 5, "maximum": 15, "step": 3}
    )

    set_value_calls = async_mock_service(hass, DOMAIN, "set_value")

    # These calls should do nothing as entity already in desired state
    await async_reproduce_state(
        hass,
        [
            State("counter.entity", "5"),
            State("counter.entity_attr", "8"),
        ],
    )

    assert len(set_value_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("counter.entity", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(set_value_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("counter.entity", "2"),
            State("counter.entity_attr", "7", {"minimum": 3, "maximum": 21, "step": 5}),
            # Should not raise
            State("counter.non_existing", "6"),
        ],
    )

    valid_calls = [
        {"entity_id": "counter.entity", "value": "2"},
        {"entity_id": "counter.entity_attr", "value": "7"},
    ]
    assert len(set_value_calls) == 2
    for call in set_value_calls:
        assert call.domain == "counter"
        assert call.data in valid_calls
        valid_calls.remove(call.data)
