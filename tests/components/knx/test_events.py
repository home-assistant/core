"""Test KNX events."""

import logging

import pytest

from homeassistant.components.knx import CONF_EVENT, CONF_TYPE, KNX_ADDRESS
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import async_capture_events


async def test_knx_event(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    knx: KNXTestKit,
) -> None:
    """Test the `knx_event` event."""
    test_group_a = "0/4/*"
    test_address_a_1 = "0/4/0"
    test_address_a_2 = "0/4/100"
    test_group_b = "1/3-6/*"
    test_address_b_1 = "1/3/0"
    test_address_b_2 = "1/6/200"
    test_group_c = "2/6/4,5"
    test_address_c_1 = "2/6/4"
    test_address_c_2 = "2/6/5"
    test_address_d = "5/4/3"
    events = async_capture_events(hass, "knx_event")

    async def test_event_data(address, payload, value=None):
        await hass.async_block_till_done()
        assert len(events) == 1
        event = events.pop()
        assert event.data["data"] == payload
        assert event.data["value"] == value
        assert event.data["direction"] == "Incoming"
        assert event.data["destination"] == address
        if payload is None:
            assert event.data["telegramtype"] == "GroupValueRead"
        else:
            assert event.data["telegramtype"] in (
                "GroupValueWrite",
                "GroupValueResponse",
            )
        assert event.data["source"] == KNXTestKit.INDIVIDUAL_ADDRESS

    await knx.setup_integration(
        {
            CONF_EVENT: [
                {
                    KNX_ADDRESS: [
                        test_group_a,
                        test_group_b,
                    ],
                    CONF_TYPE: "2byte_unsigned",
                },
                {
                    KNX_ADDRESS: test_group_c,
                    CONF_TYPE: "2byte_float",
                },
                {
                    KNX_ADDRESS: [test_address_d],
                },
            ],
        }
    )

    # no event received
    await hass.async_block_till_done()
    assert len(events) == 0

    # receive telegrams for group addresses matching the filter
    await knx.receive_write(test_address_a_1, (0x03, 0x2F))
    await test_event_data(test_address_a_1, (0x03, 0x2F), value=815)

    await knx.receive_response(test_address_a_2, (0x12, 0x67))
    await test_event_data(test_address_a_2, (0x12, 0x67), value=4711)

    await knx.receive_write(test_address_b_1, (0, 0))
    await test_event_data(test_address_b_1, (0, 0), value=0)

    await knx.receive_response(test_address_b_2, (255, 255))
    await test_event_data(test_address_b_2, (255, 255), value=65535)

    await knx.receive_write(test_address_c_1, (0x06, 0xA0))
    await test_event_data(test_address_c_1, (0x06, 0xA0), value=16.96)

    await knx.receive_response(test_address_c_2, (0x8A, 0x24))
    await test_event_data(test_address_c_2, (0x8A, 0x24), value=-30.0)

    await knx.receive_read(test_address_d)
    await test_event_data(test_address_d, None)

    await knx.receive_write(test_address_d, True)
    await test_event_data(test_address_d, True)

    # receive telegrams for group addresses not matching any filter
    await knx.receive_write("0/5/0", True)
    await knx.receive_write("1/7/0", True)
    await knx.receive_write("2/6/6", True)
    await hass.async_block_till_done()
    assert len(events) == 0

    # receive telegrams with wrong payload length
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        await knx.receive_write(test_address_a_1, (0x03, 0x2F, 0xFF))
        assert len(caplog.messages) == 1
        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert (
            "Error in `knx_event` at decoding type "
            "'DPT2ByteUnsigned' from telegram" in record.message
        )
    await test_event_data(test_address_a_1, (0x03, 0x2F, 0xFF), value=None)
