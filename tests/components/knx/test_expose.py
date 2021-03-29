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


async def setup_knx_integration(hass, knx_mock, config=None):
    """Create the KNX gateway."""
    if config is None:
        config = {}
    with patch("homeassistant.components.knx.XKNX", return_value=knx_mock):
        await async_setup_component(
            hass, KNX_DOMAIN, KNX_CONFIG_SCHEMA({KNX_DOMAIN: config})
        )
        await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def xknx_mock():
    """Create a simple XKNX mock."""
    xknx_mock = Mock()
    xknx_mock.telegrams = AsyncMock()
    xknx_mock.start = AsyncMock()
    xknx_mock.stop = AsyncMock()
    return xknx_mock


async def test_binary_expose(hass, xknx_mock):
    """Test that a binary expose sends only telegrams on state change."""
    entity_id = "fake.entity"
    await setup_knx_integration(
        hass,
        xknx_mock,
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
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    assert xknx_mock.telegrams.put.call_count == 1, "Expected telegram for state change"

    # Change attribute; keep state
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {"brightness": 180})
    await hass.async_block_till_done()
    assert (
        xknx_mock.telegrams.put.call_count == 0
    ), "Expected no telegram; state not changed"

    # Change attribute and state
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "off", {"brightness": 0})
    await hass.async_block_till_done()
    assert xknx_mock.telegrams.put.call_count == 1, "Expected telegram for state change"


async def test_expose_attribute(hass, xknx_mock):
    """Test that an expose sends only telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await setup_knx_integration(
        hass,
        xknx_mock,
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
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {})
    await hass.async_block_till_done()
    assert xknx_mock.telegrams.put.call_count == 0

    # Change attribute; keep state
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await hass.async_block_till_done()
    assert xknx_mock.telegrams.put.call_count == 1

    # Change state keep attribute
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await hass.async_block_till_done()
    assert xknx_mock.telegrams.put.call_count == 0

    # Change state and attribute
    xknx_mock.reset_mock()
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await hass.async_block_till_done()
    assert xknx_mock.telegrams.put.call_count == 1
