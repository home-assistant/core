"""Test reproduce state for Lawn Mower."""
from homeassistant.components.lawn_mower import (
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_STOP,
    STATE_DOCKED,
    STATE_MOWING,
    STATE_RETURNING,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
)
from homeassistant.core import State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing lawn_mower states."""
    hass.states.async_set("lawn_mower.entity_off", STATE_OFF, {})
    hass.states.async_set("lawn_mower.entity_on", STATE_ON, {})
    hass.states.async_set("lawn_mower.entity_mowing", STATE_MOWING, {})
    hass.states.async_set("lawn_mower.entity_docked", STATE_DOCKED, {})
    hass.states.async_set("lawn_mower.entity_idle", STATE_IDLE, {})
    hass.states.async_set("lawn_mower.entity_returning", STATE_RETURNING, {})
    hass.states.async_set("lawn_mower.entity_paused", STATE_PAUSED, {})

    turn_on_calls = async_mock_service(hass, "lawn_mower", SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, "lawn_mower", SERVICE_TURN_OFF)
    start_calls = async_mock_service(hass, "lawn_mower", SERVICE_START)
    pause_calls = async_mock_service(hass, "lawn_mower", SERVICE_PAUSE)
    stop_calls = async_mock_service(hass, "lawn_mower", SERVICE_STOP)
    return_calls = async_mock_service(hass, "lawn_mower", SERVICE_RETURN_TO_BASE)

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("lawn_mower.entity_off", STATE_OFF),
            State("lawn_mower.entity_on", STATE_ON),
            State("lawn_mower.entity_mowing", STATE_MOWING),
            State("lawn_mower.entity_docked", STATE_DOCKED),
            State("lawn_mower.entity_idle", STATE_IDLE),
            State("lawn_mower.entity_returning", STATE_RETURNING),
            State("lawn_mower.entity_paused", STATE_PAUSED),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(stop_calls) == 0
    assert len(return_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("lawn_mower.entity_off", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(stop_calls) == 0
    assert len(return_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("lawn_mower.entity_off", STATE_ON),
            State("lawn_mower.entity_on", STATE_OFF),
            State("lawn_mower.entity_mowing", STATE_PAUSED),
            State("lawn_mower.entity_docked", STATE_MOWING),
            State("lawn_mower.entity_idle", STATE_DOCKED),
            State("lawn_mower.entity_returning", STATE_MOWING),
            State("lawn_mower.entity_paused", STATE_IDLE),
            # Should not raise
            State("lawn_mower.non_existing", STATE_ON),
        ],
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "lawn_mower"
    assert turn_on_calls[0].data == {"entity_id": "lawn_mower.entity_off"}

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "lawn_mower"
    assert turn_off_calls[0].data == {"entity_id": "lawn_mower.entity_on"}

    assert len(start_calls) == 2
    entities = [
        {"entity_id": "lawn_mower.entity_docked"},
        {"entity_id": "lawn_mower.entity_returning"},
    ]
    for call in start_calls:
        assert call.domain == "lawn_mower"
        assert call.data in entities
        entities.remove(call.data)

    assert len(pause_calls) == 1
    assert pause_calls[0].domain == "lawn_mower"
    assert pause_calls[0].data == {"entity_id": "lawn_mower.entity_mowing"}

    assert len(stop_calls) == 1
    assert stop_calls[0].domain == "lawn_mower"
    assert stop_calls[0].data == {"entity_id": "lawn_mower.entity_paused"}

    assert len(return_calls) == 1
    assert return_calls[0].domain == "lawn_mower"
    assert return_calls[0].data == {"entity_id": "lawn_mower.entity_idle"}
