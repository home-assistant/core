"""Test KNX select."""
import pytest

from homeassistant.components.knx.const import (
    CONF_PAYLOAD_LENGTH,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    KNX_ADDRESS,
)
from homeassistant.components.knx.schema import SelectSchema
from homeassistant.const import CONF_NAME, CONF_PAYLOAD, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_select_dpt_2_simple(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test simple KNX select."""
    _options = [
        {CONF_PAYLOAD: 0b00, SelectSchema.CONF_OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectSchema.CONF_OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectSchema.CONF_OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_SYNC_STATE: False,
                CONF_PAYLOAD_LENGTH: 0,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
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

    # select invalid option
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.test", "option": "invalid"},
            blocking=True,
        )
    await knx.assert_no_telegram()


async def test_select_dpt_2_restore(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX select with passive_address and respond_to_read restoring state."""
    _options = [
        {CONF_PAYLOAD: 0b00, SelectSchema.CONF_OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectSchema.CONF_OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectSchema.CONF_OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    test_passive_address = "3/3/3"
    fake_state = State("select.test", "Control - On")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
                CONF_PAYLOAD_LENGTH: 0,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("select.test")
    assert state.state == "Control - On"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(test_address, 3)

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()


async def test_select_dpt_20_103_all_options(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX select with state_address, passive_address and respond_to_read."""
    _options = [
        {CONF_PAYLOAD: 0, SelectSchema.CONF_OPTION: "Auto"},
        {CONF_PAYLOAD: 1, SelectSchema.CONF_OPTION: "Legio protect"},
        {CONF_PAYLOAD: 2, SelectSchema.CONF_OPTION: "Normal"},
        {CONF_PAYLOAD: 3, SelectSchema.CONF_OPTION: "Reduced"},
        {CONF_PAYLOAD: 4, SelectSchema.CONF_OPTION: "Off"},
    ]
    test_address = "1/1/1"
    test_state_address = "2/2/2"
    test_passive_address = "3/3/3"

    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_STATE_ADDRESS: test_state_address,
                CONF_RESPOND_TO_READ: True,
                CONF_PAYLOAD_LENGTH: 1,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
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
