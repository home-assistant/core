"""Test Z-Wave Lights."""
from homeassistant.components.ozw.light import byte_to_zwave_brightness

from .common import setup_ozw


async def test_light(hass, light_data, light_msg, light_rgb_msg, sent_messages):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=light_data)

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

    # Test setting color_name
    new_color = "blue"
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "color_name": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 9

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#0000ff0000", "ValueIDKey": 659341335}

    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 255, "ValueIDKey": 659128337}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#0000ff0000"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["rgb_color"] == (0, 0, 255)

    # Test setting hs_color
    new_color = [300, 70]
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "hs_color": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 11
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 255, "ValueIDKey": 659128337}

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#ff4cff0000", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#ff4cff0000"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["hs_color"] == (300.0, 70.196)

    # Test setting rgb_color
    new_color = [255, 154, 0]
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "rgb_color": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 13
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 255, "ValueIDKey": 659128337}

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#ff99000000", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#ff99000000"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["rgb_color"] == (255, 153, 0)

    # Test setting xy_color
    new_color = [0.52, 0.43]
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "xy_color": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 15
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 255, "ValueIDKey": 659128337}

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#ffbb370000", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#ffbb370000"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["xy_color"] == (0.519, 0.429)

    # Test setting color temp
    new_color = 465
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "color_temp": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 17
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 255, "ValueIDKey": 659128337}

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#000000e51a", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#000000e51a"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_temp"] == 465

    # Test setting invalid color temp
    new_color = 120
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "color_temp": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 19
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 255, "ValueIDKey": 659128337}

    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#00000000ff", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#00000000ff"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_temp"] == 154


async def test_no_rgb_light(hass, light_no_rgb_data, light_no_rgb_msg, sent_messages):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=light_no_rgb_data)

    # Test loaded no RGBW support (dimmer only)
    state = hass.states.get("light.master_bedroom_l_level")
    assert state is not None
    assert state.state == "off"

    # Turn on the light
    new_brightness = 44
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.master_bedroom_l_level", "brightness": new_brightness},
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[-1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": byte_to_zwave_brightness(new_brightness),
        "ValueIDKey": 38371345,
    }

    # Feedback on state

    light_no_rgb_msg.decode()
    light_no_rgb_msg.payload["Value"] = byte_to_zwave_brightness(new_brightness)
    light_no_rgb_msg.encode()
    receive_message(light_no_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.master_bedroom_l_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == new_brightness


async def test_no_ww_light(
    hass, light_no_ww_data, light_msg, light_rgb_msg, sent_messages
):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=light_no_ww_data)

    # Test loaded no ww support
    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"

    # Turn on the light
    white_color = 190
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "white_value": white_color,
        },
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#00000000be", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#00000000be"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["white_value"] == 190


async def test_no_cw_light(
    hass, light_no_cw_data, light_msg, light_rgb_msg, sent_messages
):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=light_no_cw_data)

    # Test loaded no cw support
    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"

    # Turn on the light
    white_color = 190
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "white_value": white_color,
        },
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#000000be00", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#000000be00"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["white_value"] == 190


async def test_wc_light(hass, light_wc_data, light_msg, light_rgb_msg, sent_messages):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=light_wc_data)

    # Test loaded only white LED support
    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"

    # Turn on the light
    new_color = 190
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.led_bulb_6_multi_colour_level", "color_temp": new_color},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[-2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": "#0000001be4", "ValueIDKey": 659341335}

    # Feedback on state
    light_msg.decode()
    light_msg.payload["Value"] = byte_to_zwave_brightness(255)
    light_msg.encode()
    light_rgb_msg.decode()
    light_rgb_msg.payload["Value"] = "#0000001be4"
    light_rgb_msg.encode()
    receive_message(light_msg)
    receive_message(light_rgb_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["color_temp"] == 191
