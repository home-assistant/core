"""Test knx expose."""


from homeassistant.components.knx import CONF_KNX_EXPOSE, KNX_ADDRESS
from homeassistant.const import CONF_ATTRIBUTE, CONF_ENTITY_ID, CONF_TYPE

from . import setup_knx_integration


async def test_binary_expose(hass, knx_ip_interface_mock):
    """Test that a binary expose sends only telegrams on state change."""
    entity_id = "fake.entity"
    await setup_knx_integration(
        hass,
        knx_ip_interface_mock,
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "binary",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to on
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    assert (
        knx_ip_interface_mock.send_telegram.call_count == 1
    ), "Expected telegram for state change"

    # Change attribute; keep state
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {"brightness": 180})
    await hass.async_block_till_done()
    assert (
        knx_ip_interface_mock.send_telegram.call_count == 0
    ), "Expected no telegram; state not changed"

    # Change attribute and state
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "off", {"brightness": 0})
    await hass.async_block_till_done()
    assert (
        knx_ip_interface_mock.send_telegram.call_count == 1
    ), "Expected telegram for state change"


async def test_expose_attribute(hass, knx_ip_interface_mock):
    """Test that an expose sends only telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await setup_knx_integration(
        hass,
        knx_ip_interface_mock,
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to on; no attribute
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    assert knx_ip_interface_mock.send_telegram.call_count == 0

    # Change attribute; keep state
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    assert knx_ip_interface_mock.send_telegram.call_count == 1

    # Change state keep attribute
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await hass.async_block_till_done()
    assert knx_ip_interface_mock.send_telegram.call_count == 0

    # Change state and attribute
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await hass.async_block_till_done()
    assert knx_ip_interface_mock.send_telegram.call_count == 1
