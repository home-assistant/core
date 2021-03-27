"""Test knx expose."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.knx import (
    CONF_KNX_EXPOSE,
    CONFIG_SCHEMA as KNX_CONFIG_SCHEMA,
    KNX_ADDRESS,
)
from homeassistant.components.knx.const import DOMAIN as KNX_DOMAIN
from homeassistant.const import CONF_ATTRIBUTE, CONF_ENTITY_ID, CONF_TYPE
from homeassistant.setup import async_setup_component


async def setup_knx_integration(hass, knx_mock, config={}):
    """Create the KNX gateway."""
    with patch("homeassistant.components.knx.XKNX", return_value=knx_mock):
        await async_setup_component(
            hass, KNX_DOMAIN, KNX_CONFIG_SCHEMA({KNX_DOMAIN: config})
        )
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def xknxMock():
    """Create a simple XKNX mock."""
    xknxMock = Mock()
    xknxMock.telegrams = AsyncMock()
    xknxMock.start = AsyncMock()
    xknxMock.stop = AsyncMock()
    return xknxMock


async def test_binary_expose(hass, xknxMock):
    """Test that a binary expose sends only telegrams on state change."""
    e_id = "fake.entity"
    await setup_knx_integration(
        hass,
        xknxMock,
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "binary",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: e_id,
            }
        },
    )
    assert len(hass.states.async_all()) == 0

    # Change state to on
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "on", {})
    await hass.async_block_till_done()
    assert xknxMock.telegrams.put.call_count == 1, "Expected telegram for state change"

    # Change attribute; keep state
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "on", {"brightness": 180})
    await hass.async_block_till_done()
    assert (
        xknxMock.telegrams.put.call_count == 0
    ), "Expected no telegram; state not changed"

    # Change attribute and state
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "off", {"brightness": 0})
    await hass.async_block_till_done()
    assert xknxMock.telegrams.put.call_count == 1, "Expected telegram for state change"


async def test_expose_attribute(hass, xknxMock):
    """Test that an expose sends only telegrams on attribute change."""
    e_id = "fake.entity"
    a_id = "fakeAttribute"
    await setup_knx_integration(
        hass,
        xknxMock,
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: e_id,
                CONF_ATTRIBUTE: a_id,
            }
        },
    )
    assert len(hass.states.async_all()) == 0

    # Change state to on; no attribute
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "on", {})
    await hass.async_block_till_done()
    assert xknxMock.telegrams.put.call_count == 0

    # Change attribute; keep state
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "on", {a_id: 1})
    await hass.async_block_till_done()
    assert xknxMock.telegrams.put.call_count == 1

    # Change state keep attribute
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "off", {a_id: 1})
    await hass.async_block_till_done()
    assert xknxMock.telegrams.put.call_count == 0

    # Change state and attribute
    xknxMock.reset_mock()
    hass.states.async_set(e_id, "on", {a_id: 0})
    await hass.async_block_till_done()
    assert xknxMock.telegrams.put.call_count == 1
