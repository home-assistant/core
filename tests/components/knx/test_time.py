"""Test KNX time."""
from homeassistant.components.knx.const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from homeassistant.components.knx.schema import TimeSchema
from homeassistant.components.time import ATTR_TIME, DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State

from .conftest import KNXTestKit

from tests.common import mock_restore_cache


async def test_time(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX time."""
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            TimeSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    # set value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "time.test", ATTR_TIME: "01:02:03"},
        blocking=True,
    )
    await knx.assert_write(
        test_address,
        (0x01, 0x02, 0x03),
    )
    state = hass.states.get("time.test")
    assert state.state == "01:02:03"

    # update from KNX
    await knx.receive_write(
        test_address,
        (0x0C, 0x10, 0x3B),
    )
    state = hass.states.get("time.test")
    assert state.state == "12:16:59"


async def test_time_restore_and_respond(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX time with passive_address, restoring state and respond_to_read."""
    test_address = "1/1/1"
    test_passive_address = "3/3/3"

    fake_state = State("time.test", "01:02:03")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            TimeSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("time.test")
    assert state.state == "01:02:03"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(
        test_address,
        (0x01, 0x02, 0x03),
    )

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(
        test_passive_address,
        (0x0C, 0x00, 0x00),
    )
    state = hass.states.get("time.test")
    assert state.state == "12:00:00"
