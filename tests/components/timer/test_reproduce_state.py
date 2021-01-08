"""Test reproduce state for Timer."""
from homeassistant.components.timer import (
    ATTR_DURATION,
    SERVICE_CANCEL,
    SERVICE_PAUSE,
    SERVICE_START,
    STATUS_ACTIVE,
    STATUS_IDLE,
    STATUS_PAUSED,
)
from homeassistant.core import State

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Timer states."""
    hass.states.async_set("timer.entity_idle", STATUS_IDLE, {})
    hass.states.async_set("timer.entity_paused", STATUS_PAUSED, {})
    hass.states.async_set("timer.entity_active", STATUS_ACTIVE, {})
    hass.states.async_set(
        "timer.entity_active_attr", STATUS_ACTIVE, {ATTR_DURATION: "00:01:00"}
    )

    start_calls = async_mock_service(hass, "timer", SERVICE_START)
    pause_calls = async_mock_service(hass, "timer", SERVICE_PAUSE)
    cancel_calls = async_mock_service(hass, "timer", SERVICE_CANCEL)

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("timer.entity_idle", STATUS_IDLE),
            State("timer.entity_paused", STATUS_PAUSED),
            State("timer.entity_active", STATUS_ACTIVE),
            State(
                "timer.entity_active_attr", STATUS_ACTIVE, {ATTR_DURATION: "00:01:00"}
            ),
        ],
    )

    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(cancel_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("timer.entity_idle", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(cancel_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("timer.entity_idle", STATUS_ACTIVE, {ATTR_DURATION: "00:01:00"}),
            State("timer.entity_paused", STATUS_ACTIVE),
            State("timer.entity_active", STATUS_IDLE),
            State("timer.entity_active_attr", STATUS_PAUSED),
            # Should not raise
            State("timer.non_existing", "on"),
        ],
    )

    valid_start_calls = [
        {"entity_id": "timer.entity_idle", ATTR_DURATION: "00:01:00"},
        {"entity_id": "timer.entity_paused"},
    ]
    assert len(start_calls) == 2
    for call in start_calls:
        assert call.domain == "timer"
        assert call.data in valid_start_calls
        valid_start_calls.remove(call.data)

    assert len(pause_calls) == 1
    assert pause_calls[0].domain == "timer"
    assert pause_calls[0].data == {"entity_id": "timer.entity_active_attr"}

    assert len(cancel_calls) == 1
    assert cancel_calls[0].domain == "timer"
    assert cancel_calls[0].data == {"entity_id": "timer.entity_active"}
