"""Test knx expose."""

from homeassistant.components.knx import CONF_KNX_EXPOSE, KNX_ADDRESS
from homeassistant.const import CONF_ATTRIBUTE, CONF_ENTITY_ID, CONF_TYPE

from . import setup_knx_integration

from tests.components.knx.conftest import KNXIPMock


async def test_binary_expose(hass, knx_ip_interface_mock: KNXIPMock):
    """Test that a binary expose sends only telegrams on state change."""
    entity_id = "fake.entity"
    ga_expose = "1/1/8"
    await setup_knx_integration(
        hass,
        knx_ip_interface_mock,
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "binary",
                KNX_ADDRESS: ga_expose,
                CONF_ENTITY_ID: entity_id,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to on
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    knx_ip_interface_mock.assert_telegrams_gas([ga_expose], "state change")

    # Change attribute; keep state
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {"brightness": 180})
    await hass.async_block_till_done()
    knx_ip_interface_mock.assert_telegrams_gas([], "state not changed")

    # Change attribute and state
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "off", {"brightness": 0})
    await hass.async_block_till_done()
    knx_ip_interface_mock.assert_telegrams_gas([ga_expose], "state change")


async def test_expose_attribute(hass, knx_ip_interface_mock):
    """Test that an expose sends only telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    ga_expose = "1/1/8"
    await setup_knx_integration(
        hass,
        knx_ip_interface_mock,
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: ga_expose,
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
    knx_ip_interface_mock.assert_telegrams_gas([], "no attribute change")

    # Change attribute; keep state
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    knx_ip_interface_mock.assert_telegrams_gas([ga_expose], "attribute change")

    # Change state keep attribute
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await hass.async_block_till_done()
    knx_ip_interface_mock.assert_telegrams_gas([], "no attribute change")

    # Change state and attribute
    knx_ip_interface_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await hass.async_block_till_done()
    knx_ip_interface_mock.assert_telegrams_gas([ga_expose], "attribute change")
