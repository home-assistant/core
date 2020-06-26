"""Test Z-Wave Locks."""
from .common import setup_ozw


async def test_lock(hass, lock_data, sent_messages, lock_msg):
    """Test lock."""
    receive_message = await setup_ozw(hass, fixture=lock_data)

    # Test loaded
    state = hass.states.get("lock.danalock_v3_btze_locked")
    assert state is not None
    assert state.state == "unlocked"

    # Test locking
    await hass.services.async_call(
        "lock", "lock", {"entity_id": "lock.danalock_v3_btze_locked"}, blocking=True
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": True, "ValueIDKey": 173572112}

    # Feedback on state
    lock_msg.decode()
    lock_msg.payload["Value"] = True
    lock_msg.encode()
    receive_message(lock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("lock.danalock_v3_btze_locked")
    assert state is not None
    assert state.state == "locked"

    # Test unlocking
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": "lock.danalock_v3_btze_locked"}, blocking=True
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 173572112}
