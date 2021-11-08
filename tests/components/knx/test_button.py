"""Test KNX button."""
from datetime import timedelta

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import ButtonSchema
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed


async def test_button_raw(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX button with raw payload."""
    events = async_capture_events(hass, "state_changed")
    await knx.setup_integration(
        {
            ButtonSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                ButtonSchema.CONF_PAYLOAD: True,
                ButtonSchema.CONF_PAYLOAD_LENGTH: 0,
            }
        }
    )
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    # press button
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", True)
    assert len(events) == 1
    events.pop()

    # received telegrams on button GA are ignored by the entity
    old_state = hass.states.get("button.test")
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=3))
    await knx.receive_write("1/2/3", False)
    await knx.receive_write("1/2/3", True)
    new_state = hass.states.get("button.test")
    assert old_state == new_state
    assert len(events) == 0

    # button does not respond to read
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_button_type(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX button with encoded payload."""
    events = async_capture_events(hass, "state_changed")
    await knx.setup_integration(
        {
            ButtonSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                ButtonSchema.CONF_PAYLOAD: 21.0,
                CONF_TYPE: "2byte_float",
            }
        }
    )
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    # press button
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (0x0C, 0x1A))
    assert len(events) == 1
