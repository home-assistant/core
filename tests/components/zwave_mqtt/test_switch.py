"""Test Z-Wave Switches."""
from .common import setup_zwave


async def test_switch(hass, generic_data, sent_messages, switch_msg):
    """Test setting up config entry."""
    receive_message = await setup_zwave(hass, fixture=generic_data)

    # Test loaded
    state = hass.states.get("switch.smart_plug_switch")
    assert state is not None
    assert state.state == "off"

    # Test turning on
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.smart_plug_switch"}, blocking=True
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": True, "ValueIDKey": 541671440}

    # Feedback on state
    switch_msg.decode()
    switch_msg.payload["Value"] = True
    switch_msg.encode()
    receive_message(switch_msg)
    await hass.async_block_till_done()

    state = hass.states.get("switch.smart_plug_switch")
    assert state is not None
    assert state.state == "on"

    # Test turning off
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.smart_plug_switch"}, blocking=True
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 541671440}
