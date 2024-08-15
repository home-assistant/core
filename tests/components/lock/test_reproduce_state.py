"""Test reproduce state for Lock."""

import pytest

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Lock states."""
    hass.states.async_set("lock.entity_locked", "locked", {})
    hass.states.async_set("lock.entity_unlocked", "unlocked", {})
    hass.states.async_set("lock.entity_opened", "open", {})

    lock_calls = async_mock_service(hass, "lock", "lock")
    unlock_calls = async_mock_service(hass, "lock", "unlock")
    open_calls = async_mock_service(hass, "lock", "open")

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("lock.entity_locked", "locked"),
            State("lock.entity_unlocked", "unlocked", {}),
            State("lock.entity_opened", "open", {}),
        ],
    )

    assert len(lock_calls) == 0
    assert len(unlock_calls) == 0
    assert len(open_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("lock.entity_locked", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(lock_calls) == 0
    assert len(unlock_calls) == 0
    assert len(open_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("lock.entity_locked", "open"),
            State("lock.entity_unlocked", "locked"),
            State("lock.entity_opened", "unlocked"),
            # Should not raise
            State("lock.non_existing", "on"),
        ],
    )

    assert len(lock_calls) == 1
    assert lock_calls[0].domain == "lock"
    assert lock_calls[0].data == {"entity_id": "lock.entity_unlocked"}

    assert len(unlock_calls) == 1
    assert unlock_calls[0].domain == "lock"
    assert unlock_calls[0].data == {"entity_id": "lock.entity_opened"}

    assert len(open_calls) == 1
    assert open_calls[0].domain == "lock"
    assert open_calls[0].data == {"entity_id": "lock.entity_locked"}
