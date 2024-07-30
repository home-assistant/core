"""Tests for the Lutron Caseta integration."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import MockBridge, async_setup_integration


async def test_button_press_and_release(hass: HomeAssistant) -> None:
    """Test a button press and delayed release."""
    _, mock_bridge = await async_setup_integration(hass, MockBridge)

    button_contact_sensor_entity_id = "binary_sensor.dining_room_pico_stop_favorite"

    state = hass.states.get(button_contact_sensor_entity_id)
    assert state
    assert state.state == STATE_OFF

    callback = mock_bridge.button_subscribers["111"][0]

    callback("Press")
    await hass.async_block_till_done()

    state = hass.states.get(button_contact_sensor_entity_id)
    assert state.state == STATE_ON

    callback("Released")
    await hass.async_block_till_done()

    state = hass.states.get(button_contact_sensor_entity_id)
    assert state.state == STATE_OFF
