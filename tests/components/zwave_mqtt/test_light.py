"""Test Z-Wave Lights."""
from homeassistant.components.zwave_mqtt.light import byte_to_zwave_brightness

from .common import setup_zwave


async def test_light(hass, sent_messages):
    """Test setting up config entry."""
    await setup_zwave(hass, "generic_network_dump.csv")

    # Test loaded
    state = hass.states.get("light.led_bulb_6_multi_colour_level")
    assert state is not None
    assert state.state == "off"

    # Test turning on
    new_brightness = 45
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.led_bulb_6_multi_colour_level",
            "brightness": new_brightness,
        },
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {
        "Value": byte_to_zwave_brightness(new_brightness),
        "ValueIDKey": 659128337,
    }

    # Test turning off
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.led_bulb_6_multi_colour_level"},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 659128337}
