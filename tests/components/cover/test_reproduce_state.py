"""Test reproduce state for Cover."""
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Cover states."""
    hass.states.async_set("cover.entity_close", STATE_CLOSED, {})
    hass.states.async_set(
        "cover.entity_close_attr",
        STATE_CLOSED,
        {ATTR_CURRENT_POSITION: 0, ATTR_CURRENT_TILT_POSITION: 0},
    )
    hass.states.async_set(
        "cover.entity_close_tilt", STATE_CLOSED, {ATTR_CURRENT_TILT_POSITION: 50}
    )
    hass.states.async_set("cover.entity_open", STATE_OPEN, {})
    hass.states.async_set(
        "cover.entity_slightly_open", STATE_OPEN, {ATTR_CURRENT_POSITION: 50}
    )
    hass.states.async_set(
        "cover.entity_open_attr",
        STATE_OPEN,
        {ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 0},
    )
    hass.states.async_set(
        "cover.entity_open_tilt",
        STATE_OPEN,
        {ATTR_CURRENT_POSITION: 50, ATTR_CURRENT_TILT_POSITION: 50},
    )
    hass.states.async_set(
        "cover.entity_entirely_open",
        STATE_OPEN,
        {ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 100},
    )

    close_calls = async_mock_service(hass, "cover", SERVICE_CLOSE_COVER)
    open_calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)
    close_tilt_calls = async_mock_service(hass, "cover", SERVICE_CLOSE_COVER_TILT)
    open_tilt_calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER_TILT)
    position_calls = async_mock_service(hass, "cover", SERVICE_SET_COVER_POSITION)
    position_tilt_calls = async_mock_service(
        hass, "cover", SERVICE_SET_COVER_TILT_POSITION
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("cover.entity_close", STATE_CLOSED),
            State(
                "cover.entity_close_attr",
                STATE_CLOSED,
                {ATTR_CURRENT_POSITION: 0, ATTR_CURRENT_TILT_POSITION: 0},
            ),
            State(
                "cover.entity_close_tilt",
                STATE_CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State("cover.entity_open", STATE_OPEN),
            State(
                "cover.entity_slightly_open", STATE_OPEN, {ATTR_CURRENT_POSITION: 50}
            ),
            State(
                "cover.entity_open_attr",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 0},
            ),
            State(
                "cover.entity_open_tilt",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 50, ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State(
                "cover.entity_entirely_open",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 100},
            ),
        ],
    )

    assert len(close_calls) == 0
    assert len(open_calls) == 0
    assert len(close_tilt_calls) == 0
    assert len(open_tilt_calls) == 0
    assert len(position_calls) == 0
    assert len(position_tilt_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("cover.entity_close", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(close_calls) == 0
    assert len(open_calls) == 0
    assert len(close_tilt_calls) == 0
    assert len(open_tilt_calls) == 0
    assert len(position_calls) == 0
    assert len(position_tilt_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("cover.entity_close", STATE_OPEN),
            State(
                "cover.entity_close_attr",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 50, ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State(
                "cover.entity_close_tilt",
                STATE_CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 100},
            ),
            State("cover.entity_open", STATE_CLOSED),
            State("cover.entity_slightly_open", STATE_OPEN, {}),
            State("cover.entity_open_attr", STATE_CLOSED, {}),
            State(
                "cover.entity_open_tilt", STATE_OPEN, {ATTR_CURRENT_TILT_POSITION: 0}
            ),
            State(
                "cover.entity_entirely_open",
                STATE_CLOSED,
                {ATTR_CURRENT_POSITION: 0, ATTR_CURRENT_TILT_POSITION: 0},
            ),
            # Should not raise
            State("cover.non_existing", "on"),
        ],
    )

    valid_close_calls = [
        {"entity_id": "cover.entity_open"},
        {"entity_id": "cover.entity_open_attr"},
        {"entity_id": "cover.entity_entirely_open"},
    ]
    assert len(close_calls) == 3
    for call in close_calls:
        assert call.domain == "cover"
        assert call.data in valid_close_calls
        valid_close_calls.remove(call.data)

    valid_open_calls = [
        {"entity_id": "cover.entity_close"},
        {"entity_id": "cover.entity_slightly_open"},
        {"entity_id": "cover.entity_open_tilt"},
    ]
    assert len(open_calls) == 3
    for call in open_calls:
        assert call.domain == "cover"
        assert call.data in valid_open_calls
        valid_open_calls.remove(call.data)

    valid_close_tilt_calls = [
        {"entity_id": "cover.entity_open_tilt"},
        {"entity_id": "cover.entity_entirely_open"},
    ]
    assert len(close_tilt_calls) == 2
    for call in close_tilt_calls:
        assert call.domain == "cover"
        assert call.data in valid_close_tilt_calls
        valid_close_tilt_calls.remove(call.data)

    assert len(open_tilt_calls) == 1
    assert open_tilt_calls[0].domain == "cover"
    assert open_tilt_calls[0].data == {"entity_id": "cover.entity_close_tilt"}

    assert len(position_calls) == 1
    assert position_calls[0].domain == "cover"
    assert position_calls[0].data == {
        "entity_id": "cover.entity_close_attr",
        ATTR_POSITION: 50,
    }

    assert len(position_tilt_calls) == 1
    assert position_tilt_calls[0].domain == "cover"
    assert position_tilt_calls[0].data == {
        "entity_id": "cover.entity_close_attr",
        ATTR_TILT_POSITION: 50,
    }
