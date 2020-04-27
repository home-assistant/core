"""Test Z-Wave Switches."""
from .common import setup_zwave


async def test_switch(hass, sent_messages):
    """Test setting up config entry."""
    await setup_zwave(hass, "generic_network_dump.csv")

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

    # Test turning off
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.smart_plug_switch"}, blocking=True
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 541671440}
