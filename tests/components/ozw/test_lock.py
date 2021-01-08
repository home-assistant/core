"""Test Z-Wave Locks."""
from .common import setup_ozw


async def test_lock(hass, lock_data, sent_messages, lock_msg, caplog):
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

    # Test set_usercode
    await hass.services.async_call(
        "ozw",
        "set_usercode",
        {
            "entity_id": "lock.danalock_v3_btze_locked",
            "usercode": 123456,
            "code_slot": 1,
        },
        blocking=True,
    )
    assert len(sent_messages) == 3
    msg = sent_messages[2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "123456", "ValueIDKey": 281475150299159}

    # Test clear_usercode
    await hass.services.async_call(
        "ozw",
        "clear_usercode",
        {"entity_id": "lock.danalock_v3_btze_locked", "code_slot": 1},
        blocking=True,
    )
    assert len(sent_messages) == 5
    msg = sent_messages[4]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 1, "ValueIDKey": 72057594219905046}

    # Test set_usercode invalid length
    await hass.services.async_call(
        "ozw",
        "set_usercode",
        {
            "entity_id": "lock.danalock_v3_btze_locked",
            "usercode": "123",
            "code_slot": 1,
        },
        blocking=True,
    )
    assert len(sent_messages) == 5
    assert "User code must be at least 4 digits" in caplog.text
