"""Test reproduce state for Valve."""
import pytest

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
)
from homeassistant.const import (
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Valve states."""
    hass.states.async_set("valve.entity_close", STATE_CLOSED, {})
    hass.states.async_set(
        "valve.entity_close_attr",
        STATE_CLOSED,
        {ATTR_CURRENT_POSITION: 0},
    )
    hass.states.async_set("valve.entity_open", STATE_OPEN, {})
    hass.states.async_set(
        "valve.entity_slightly_open", STATE_OPEN, {ATTR_CURRENT_POSITION: 50}
    )
    hass.states.async_set(
        "valve.entity_open_attr",
        STATE_OPEN,
        {ATTR_CURRENT_POSITION: 100},
    )
    hass.states.async_set(
        "valve.entity_entirely_open",
        STATE_OPEN,
        {ATTR_CURRENT_POSITION: 100},
    )

    close_calls = async_mock_service(hass, "valve", SERVICE_CLOSE_VALVE)
    open_calls = async_mock_service(hass, "valve", SERVICE_OPEN_VALVE)
    position_calls = async_mock_service(hass, "valve", SERVICE_SET_VALVE_POSITION)
    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("valve.entity_close", STATE_CLOSED),
            State(
                "valve.entity_close_attr",
                STATE_CLOSED,
                {ATTR_CURRENT_POSITION: 0},
            ),
            State("valve.entity_open", STATE_OPEN),
            State(
                "valve.entity_slightly_open", STATE_OPEN, {ATTR_CURRENT_POSITION: 50}
            ),
            State(
                "valve.entity_open_attr",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 100},
            ),
        ],
    )

    assert len(close_calls) == 0
    assert len(open_calls) == 0
    assert len(position_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("valve.entity_close", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(close_calls) == 0
    assert len(open_calls) == 0
    assert len(position_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("valve.entity_close", STATE_OPEN),
            State(
                "valve.entity_close_attr",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 50},
            ),
            State("valve.entity_open", STATE_CLOSED),
            State("valve.entity_slightly_open", STATE_OPEN, {}),
            State("valve.entity_open_attr", STATE_CLOSED, {}),
            State(
                "valve.entity_entirely_open",
                STATE_CLOSED,
                {ATTR_CURRENT_POSITION: 0},
            ),
            # Should not raise
            State("valve.non_existing", "on"),
        ],
    )

    valid_close_calls = [
        {"entity_id": "valve.entity_open"},
        {"entity_id": "valve.entity_open_attr"},
        {"entity_id": "valve.entity_entirely_open"},
    ]
    assert len(close_calls) == 3
    for call in close_calls:
        assert call.domain == "valve"
        assert call.data in valid_close_calls
        valid_close_calls.remove(call.data)

    valid_open_calls = [
        {"entity_id": "valve.entity_close"},
        {"entity_id": "valve.entity_slightly_open"},
    ]
    assert len(open_calls) == 3
    for call in open_calls:
        assert call.domain == "valve"
        assert call.data in valid_open_calls
        valid_open_calls.remove(call.data)

    assert len(position_calls) == 1
    assert position_calls[0].domain == "valve"
    assert position_calls[0].data == {
        "entity_id": "valve.entity_close_attr",
        ATTR_POSITION: 50,
    }
