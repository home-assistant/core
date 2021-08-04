"""Test KNX services."""
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import async_capture_events


async def test_send(hass: HomeAssistant, knx: KNXTestKit):
    """Test `knx.send` service."""
    test_address = "1/2/3"
    await knx.setup_integration({})

    # send DPT 1 telegram
    await hass.services.async_call(
        "knx", "send", {"address": test_address, "payload": True}, blocking=True
    )
    await knx.assert_write(test_address, True)

    # send raw DPT 5 telegram
    await hass.services.async_call(
        "knx", "send", {"address": test_address, "payload": [99]}, blocking=True
    )
    await knx.assert_write(test_address, (99,))

    # send "percent" DPT 5 telegram
    await hass.services.async_call(
        "knx",
        "send",
        {"address": test_address, "payload": 99, "type": "percent"},
        blocking=True,
    )
    await knx.assert_write(test_address, (0xFC,))

    # send "temperature" DPT 9 telegram
    await hass.services.async_call(
        "knx",
        "send",
        {"address": test_address, "payload": 21.0, "type": "temperature"},
        blocking=True,
    )
    await knx.assert_write(test_address, (0x0C, 0x1A))

    # send multiple telegrams
    await hass.services.async_call(
        "knx",
        "send",
        {"address": [test_address, "2/2/2", "3/3/3"], "payload": 99, "type": "percent"},
        blocking=True,
    )
    await knx.assert_write(test_address, (0xFC,))
    await knx.assert_write("2/2/2", (0xFC,))
    await knx.assert_write("3/3/3", (0xFC,))


async def test_read(hass: HomeAssistant, knx: KNXTestKit):
    """Test `knx.read` service."""
    await knx.setup_integration({})

    # send read telegram
    await hass.services.async_call("knx", "read", {"address": "1/1/1"}, blocking=True)
    await knx.assert_read("1/1/1")

    # send multiple read telegrams
    await hass.services.async_call(
        "knx",
        "read",
        {"address": ["1/1/1", "2/2/2", "3/3/3"]},
        blocking=True,
    )
    await knx.assert_read("1/1/1")
    await knx.assert_read("2/2/2")
    await knx.assert_read("3/3/3")


async def test_event_register(hass: HomeAssistant, knx: KNXTestKit):
    """Test `knx.event_register` service."""
    events = async_capture_events(hass, "knx_event")
    test_address = "1/2/3"

    await knx.setup_integration({})

    # no event registered
    await knx.receive_write(test_address, True)
    await hass.async_block_till_done()
    assert len(events) == 0

    # register event
    await hass.services.async_call(
        "knx", "event_register", {"address": test_address}, blocking=True
    )
    await knx.receive_write(test_address, True)
    await knx.receive_write(test_address, False)
    await hass.async_block_till_done()
    assert len(events) == 2

    # remove event registration - no event added
    await hass.services.async_call(
        "knx",
        "event_register",
        {"address": test_address, "remove": True},
        blocking=True,
    )
    await knx.receive_write(test_address, True)
    await hass.async_block_till_done()
    assert len(events) == 2


async def test_exposure_register(hass: HomeAssistant, knx: KNXTestKit):
    """Test `knx.exposure_register` service."""
    test_address = "1/2/3"
    test_entity = "fake.entity"
    test_attribute = "fake_attribute"

    await knx.setup_integration({})

    # no exposure registered
    hass.states.async_set(test_entity, STATE_ON, {})
    await knx.assert_no_telegram()

    # register exposure
    await hass.services.async_call(
        "knx",
        "exposure_register",
        {"address": test_address, "entity_id": test_entity, "type": "binary"},
        blocking=True,
    )
    hass.states.async_set(test_entity, STATE_OFF, {})
    await knx.assert_write(test_address, False)

    # register exposure
    await hass.services.async_call(
        "knx",
        "exposure_register",
        {"address": test_address, "remove": True},
        blocking=True,
    )
    hass.states.async_set(test_entity, STATE_ON, {})
    await knx.assert_no_telegram()

    # register exposure for attribute with default
    await hass.services.async_call(
        "knx",
        "exposure_register",
        {
            "address": test_address,
            "entity_id": test_entity,
            "attribute": test_attribute,
            "type": "percentU8",
            "default": 0,
        },
        blocking=True,
    )
    # no attribute on first change wouldn't work because no attribute change since last test
    hass.states.async_set(test_entity, STATE_ON, {test_attribute: 30})
    await knx.assert_write(test_address, (30,))
    hass.states.async_set(test_entity, STATE_OFF, {})
    await knx.assert_write(test_address, (0,))
    # don't send same value sequentially
    hass.states.async_set(test_entity, STATE_ON, {test_attribute: 25})
    hass.states.async_set(test_entity, STATE_ON, {test_attribute: 25})
    hass.states.async_set(test_entity, STATE_ON, {test_attribute: 25, "unrelated": 2})
    hass.states.async_set(test_entity, STATE_OFF, {test_attribute: 25})
    await knx.assert_telegram_count(1)
    await knx.assert_write(test_address, (25,))
