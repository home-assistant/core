"""Test Z-Wave Fans."""
import pytest

from .common import setup_ozw


async def test_fan(hass, fan_data, fan_msg, sent_messages, caplog):
    """Test fan."""
    receive_message = await setup_ozw(hass, fixture=fan_data)

    # Test loaded
    state = hass.states.get("fan.in_wall_smart_fan_control_level")
    assert state is not None
    assert state.state == "on"

    # Test turning off
    await hass.services.async_call(
        "fan",
        "turn_off",
        {"entity_id": "fan.in_wall_smart_fan_control_level"},
        blocking=True,
    )

    assert len(sent_messages) == 1
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 172589073}

    # Feedback on state
    fan_msg.decode()
    fan_msg.payload["Value"] = 0
    fan_msg.encode()
    receive_message(fan_msg)
    await hass.async_block_till_done()

    state = hass.states.get("fan.in_wall_smart_fan_control_level")
    assert state is not None
    assert state.state == "off"

    # Test turning on
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.in_wall_smart_fan_control_level", "percentage": 66},
        blocking=True,
    )

    assert len(sent_messages) == 2
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 66,
        "ValueIDKey": 172589073,
    }

    # Feedback on state
    fan_msg.decode()
    fan_msg.payload["Value"] = 66
    fan_msg.encode()
    receive_message(fan_msg)
    await hass.async_block_till_done()

    state = hass.states.get("fan.in_wall_smart_fan_control_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["percentage"] == 66

    # Test turn on without speed
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": "fan.in_wall_smart_fan_control_level"},
        blocking=True,
    )

    assert len(sent_messages) == 3
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 255,
        "ValueIDKey": 172589073,
    }

    # Feedback on state
    fan_msg.decode()
    fan_msg.payload["Value"] = 99
    fan_msg.encode()
    receive_message(fan_msg)
    await hass.async_block_till_done()

    state = hass.states.get("fan.in_wall_smart_fan_control_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["percentage"] == 100

    # Test set percentage to 0
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": "fan.in_wall_smart_fan_control_level", "percentage": 0},
        blocking=True,
    )

    assert len(sent_messages) == 4
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 0,
        "ValueIDKey": 172589073,
    }

    # Feedback on state
    fan_msg.decode()
    fan_msg.payload["Value"] = 0
    fan_msg.encode()
    receive_message(fan_msg)
    await hass.async_block_till_done()

    state = hass.states.get("fan.in_wall_smart_fan_control_level")
    assert state is not None
    assert state.state == "off"

    # Test invalid speed
    new_speed = "invalid"
    with pytest.raises(ValueError):
        await hass.services.async_call(
            "fan",
            "set_speed",
            {"entity_id": "fan.in_wall_smart_fan_control_level", "speed": new_speed},
            blocking=True,
        )
