"""Test KNX events."""
from homeassistant.components.knx import CONF_KNX_EVENT_FILTER
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_knx_event(hass: HomeAssistant, knx: KNXTestKit):
    """Test `knx_event` event."""
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
    events = []

    def listener(event):
        events.append(event)

    def test_event_data(address, payload):
        assert len(events) == 1
        event = events.pop()
        assert event.data["data"] == payload
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

    hass.bus.async_listen("knx_event", listener)
    await knx.setup_integration(
        {
            CONF_KNX_EVENT_FILTER: [
                test_group_a,
                test_group_b,
                test_group_c,
                test_address_d,
            ]
        }
    )

    # no event received
    assert len(events) == 0

    # receive telegrams for group addresses matching the filter
    await knx.receive_write(test_address_a_1, True)
    test_event_data(test_address_a_1, True)

    await knx.receive_response(test_address_a_2, False)
    test_event_data(test_address_a_2, False)

    await knx.receive_write(test_address_b_1, (1,))
    test_event_data(test_address_b_1, (1,))

    await knx.receive_response(test_address_b_2, (255,))
    test_event_data(test_address_b_2, (255,))

    await knx.receive_write(test_address_c_1, (89, 43, 34, 11))
    test_event_data(test_address_c_1, (89, 43, 34, 11))

    await knx.receive_response(test_address_c_2, (255, 255, 255, 255))
    test_event_data(test_address_c_2, (255, 255, 255, 255))

    await knx.receive_read(test_address_d)
    test_event_data(test_address_d, None)

    # receive telegrams for group addresses not matching the filter
    events = []
    await knx.receive_write("0/5/0", True)
    await knx.receive_write("1/7/0", True)
    await knx.receive_write("2/6/6", True)
    assert len(events) == 0
