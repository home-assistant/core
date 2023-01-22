"""Test KNX switch."""
from homeassistant.components.knx.const import (
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    KNX_ADDRESS,
)
from homeassistant.components.knx.schema import SwitchSchema
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_switch_simple(hass: HomeAssistant, knx: KNXTestKit):
    """Test simple KNX switch."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
            }
        }
    )
    assert len(hass.states.async_all()) == 1

    # turn on switch
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", True)

    # turn off switch
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", False)

    # receive ON telegram
    await knx.receive_write("1/2/3", True)
    state = hass.states.get("switch.test")
    assert state.state is STATE_ON

    # receive OFF telegram
    await knx.receive_write("1/2/3", False)
    state = hass.states.get("switch.test")
    assert state.state is STATE_OFF

    # switch does not respond to read by default
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_switch_state(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX switch with state_address."""
    _ADDRESS = "1/1/1"
    _STATE_ADDRESS = "2/2/2"

    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: _ADDRESS,
                CONF_STATE_ADDRESS: _STATE_ADDRESS,
            },
        }
    )
    assert len(hass.states.async_all()) == 1

    # StateUpdater initialize state
    await knx.assert_read(_STATE_ADDRESS)
    await knx.receive_response(_STATE_ADDRESS, True)
    state = hass.states.get("switch.test")
    assert state.state is STATE_ON

    # receive OFF telegram at `address`
    await knx.receive_write(_ADDRESS, False)
    state = hass.states.get("switch.test")
    assert state.state is STATE_OFF

    # receive ON telegram at `address`
    await knx.receive_write(_ADDRESS, True)
    state = hass.states.get("switch.test")
    assert state.state is STATE_ON

    # receive OFF telegram at `state_address`
    await knx.receive_write(_STATE_ADDRESS, False)
    state = hass.states.get("switch.test")
    assert state.state is STATE_OFF

    # receive ON telegram at `state_address`
    await knx.receive_write(_STATE_ADDRESS, True)
    state = hass.states.get("switch.test")
    assert state.state is STATE_ON

    # turn off switch
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write(_ADDRESS, False)

    # turn on switch
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write(_ADDRESS, True)

    # switch does not respond to read by default
    await knx.receive_read(_ADDRESS)
    await knx.assert_telegram_count(0)


async def test_switch_restore_and_respond(hass, knx):
    """Test restoring KNX switch state and respond to read."""
    _ADDRESS = "1/1/1"
    fake_state = State("switch.test", "on")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: _ADDRESS,
                CONF_RESPOND_TO_READ: True,
            },
        }
    )

    # restored state - doesn't send telegram
    state = hass.states.get("switch.test")
    assert state.state == STATE_ON
    await knx.assert_telegram_count(0)

    # respond to restored state
    await knx.receive_read(_ADDRESS)
    await knx.assert_response(_ADDRESS, True)

    # turn off switch
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write(_ADDRESS, False)
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    # respond to new state
    await knx.receive_read(_ADDRESS)
    await knx.assert_response(_ADDRESS, False)
