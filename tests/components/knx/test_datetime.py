"""Test KNX date."""

from homeassistant.components.datetime import ATTR_DATETIME, DOMAIN, SERVICE_SET_VALUE
from homeassistant.components.knx.const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from homeassistant.components.knx.schema import DateTimeSchema
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State

from .conftest import KNXTestKit

from tests.common import mock_restore_cache

# KNX DPT 19.001 doesn't provide timezone information so we send local time


async def test_datetime(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX datetime."""
    # default timezone in tests is US/Pacific
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            DateTimeSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
            }
        }
    )
    # set value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": "datetime.test", ATTR_DATETIME: "2020-01-02T03:04:05+00:00"},
        blocking=True,
    )
    await knx.assert_write(
        test_address,
        (0x78, 0x01, 0x01, 0x73, 0x04, 0x05, 0x20, 0x80),
    )
    state = hass.states.get("datetime.test")
    assert state.state == "2020-01-02T03:04:05+00:00"

    # update from KNX
    await knx.receive_write(
        test_address,
        (0x7B, 0x07, 0x19, 0x49, 0x28, 0x08, 0x00, 0x00),
    )
    state = hass.states.get("datetime.test")
    assert state.state == "2023-07-25T16:40:08+00:00"


async def test_date_restore_and_respond(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX datetime with passive_address, restoring state and respond_to_read."""
    hass.config.set_time_zone("Europe/Vienna")
    test_address = "1/1/1"
    test_passive_address = "3/3/3"
    fake_state = State("datetime.test", "2022-03-03T03:04:05+00:00")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            DateTimeSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("datetime.test")
    assert state.state == "2022-03-03T03:04:05+00:00"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(
        test_address,
        (0x7A, 0x03, 0x03, 0x84, 0x04, 0x05, 0x20, 0x80),
    )

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()

    # update from KNX passive address
    await knx.receive_write(
        test_passive_address,
        (0x78, 0x01, 0x01, 0x73, 0x04, 0x05, 0x20, 0x80),
    )
    state = hass.states.get("datetime.test")
    assert state.state == "2020-01-01T18:04:05+00:00"
