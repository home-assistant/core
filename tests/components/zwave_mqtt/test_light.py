"""Test Z-Wave Lights."""
from homeassistant.components.zwave_mqtt.light import byte_to_zwave_brightness

from .common import setup_zwave


async def test_light(hass, light_data, light_msg, sent_messages):
    """Test setting up config entry."""
    receive_message = await setup_zwave(hass, fixture=light_data)

    # Test loaded
    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"

    # Test turning on
    # Beware that due to rounding, a roundtrip conversion does not always work
    new_brightness = 44
    new_transition = 0
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "brightness": new_brightness,
            "transition": new_transition,
        },
        blocking=True,
    )
    assert len(sent_messages) == 2

    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 1407375551070225}

    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": byte_to_zwave_brightness(new_brightness),
        "ValueIDKey": 659128337,
    }

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(new_brightness)
    light_msg.encode()
    receive_message(light_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == new_brightness

    # Test turning off
    new_transition = 6553
    await hass.services.async_call(
        "light",
        "turn_off",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "transition": new_transition,
        },
        blocking=True,
    )
    assert len(sent_messages) == 4

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 237, "ValueIDKey": 1407375551070225}

    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 659128337}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = 0
    light_msg.encode()
    receive_message(light_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"

    # Test turn on without brightness
    new_transition = 127
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "transition": new_transition,
        },
        blocking=True,
    )
    assert len(sent_messages) == 6

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 127, "ValueIDKey": 1407375551070225}

    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": 255,
        "ValueIDKey": 659128337,
    }

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(new_brightness)
    light_msg.encode()
    receive_message(light_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == new_brightness

    # Test set brightness to 0
    new_brightness = 0
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "brightness": new_brightness,
        },
        blocking=True,
    )
    assert len(sent_messages) == 7
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": byte_to_zwave_brightness(new_brightness),
        "ValueIDKey": 659128337,
    }

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(new_brightness)
    light_msg.encode()
    receive_message(light_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"
