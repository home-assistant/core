"""Test KNX select."""
from homeassistant.components.knx.const import (
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    KNX_ADDRESS,
)
from homeassistant.components.knx.schema import SelectSchema
from homeassistant.const import CONF_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_select_dpt_2_simple(hass: HomeAssistant, knx: KNXTestKit):
    """Test simple KNX select."""
    _options = [
        {SelectSchema.CONF_PAYLOAD: 0b00, SelectSchema.CONF_OPTION: "No control"},
        {SelectSchema.CONF_PAYLOAD: 0b10, SelectSchema.CONF_OPTION: "Control - Off"},
        {SelectSchema.CONF_PAYLOAD: 0b11, SelectSchema.CONF_OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            SelectSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_SYNC_STATE: False,
                SelectSchema.CONF_PAYLOAD_LENGTH: 0,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    assert len(hass.states.async_all()) == 1
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN

    # select an option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Control - Off"},
        blocking=True,
    )
    await knx.assert_write(test_address, 0b10)
    state = hass.states.get("select.test")
    assert state.state == "Control - Off"

    # select another option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "No control"},
        blocking=True,
    )
    await knx.assert_write(test_address, 0b00)
    state = hass.states.get("select.test")
    assert state.state == "No control"

    # don't answer to GroupValueRead requests by default
    await knx.receive_read(test_address)
    await knx.assert_no_telegram()

    # update from KNX
    await knx.receive_write(test_address, 0b11)
    state = hass.states.get("select.test")
    assert state.state == "Control - On"

    # update from KNX with undefined value
    await knx.receive_write(test_address, 0b01)
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN


async def test_select_dpt_20_103_all_options(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX select with state_address, passive_address and respond_to_read."""
    _options = [
        {SelectSchema.CONF_PAYLOAD: 0, SelectSchema.CONF_OPTION: "Auto"},
        {SelectSchema.CONF_PAYLOAD: 1, SelectSchema.CONF_OPTION: "Legio protect"},
        {SelectSchema.CONF_PAYLOAD: 2, SelectSchema.CONF_OPTION: "Normal"},
        {SelectSchema.CONF_PAYLOAD: 3, SelectSchema.CONF_OPTION: "Reduced"},
        {SelectSchema.CONF_PAYLOAD: 4, SelectSchema.CONF_OPTION: "Off"},
    ]
    test_address = "1/1/1"
    test_state_address = "2/2/2"
    test_passive_address = "3/3/3"
    await knx.setup_integration(
        {
            SelectSchema.PLATFORM_NAME: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_STATE_ADDRESS: test_state_address,
                CONF_RESPOND_TO_READ: True,
                SelectSchema.CONF_PAYLOAD_LENGTH: 1,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    assert len(hass.states.async_all()) == 1
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN

    # StateUpdater initialize state
    await knx.assert_read(test_state_address)
    await knx.receive_response(test_state_address, (2,))
    state = hass.states.get("select.test")
    assert state.state == "Normal"

    # select an option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Legio protect"},
        blocking=True,
    )
    await knx.assert_write(test_address, (1,))
    state = hass.states.get("select.test")
    assert state.state == "Legio protect"

    # answer to GroupValueRead requests
    await knx.receive_read(test_address)
    await knx.assert_response(test_address, (1,))

    # update from KNX state_address
    await knx.receive_write(test_state_address, (3,))
    state = hass.states.get("select.test")
    assert state.state == "Reduced"

    # update from KNX passive_address
    await knx.receive_write(test_passive_address, (4,))
    state = hass.states.get("select.test")
    assert state.state == "Off"
