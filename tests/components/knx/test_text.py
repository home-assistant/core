"""Test KNX number."""

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import TextSchema
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State

from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_text(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX text."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            TextSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    # set value
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": "text.test", "value": "hello world"},
        blocking=True,
    )
    await knx.assert_write(
        test_address,
        (
            0x68,
            0x65,
            0x6C,
            0x6C,
            0x6F,
            0x20,
            0x77,
            0x6F,
            0x72,
            0x6C,
            0x64,
            0x0,
            0x0,
            0x0,
        ),
    )
    state = hass.states.get("text.test")
    assert state.state == "hello world"

    # update from KNX
    await knx.receive_write(
        test_address,
        (0x68, 0x61, 0x6C, 0x6C, 0x6F, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
    )
    state = hass.states.get("text.test")
    assert state.state == "hallo"


async def test_text_restore(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX text with passive_address and restoring state."""
    test_address = "1/1/1"
    test_passive_address = "3/3/3"

    fake_state = State("text.test", "test test")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            TextSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("text.test")
    assert state.state == "test test"
    await knx.assert_telegram_count(0)

    # don't respond with restored state - xknx Notification doesn't support it yet
    await knx.receive_read(test_address)
    await knx.assert_no_telegram()

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(
        test_passive_address,
        (0x68, 0x61, 0x6C, 0x6C, 0x6F, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
    )
    state = hass.states.get("text.test")
    assert state.state == "hallo"
