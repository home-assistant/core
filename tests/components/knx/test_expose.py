"""Test knx expose."""
from unittest.mock import AsyncMock, Mock

from homeassistant.components.knx.expose import KNXExposeSensor


async def test_binary_expose(hass):
    """Test that a binary expose sends only telegrams on state change."""
    e_id = "fake.entity"
    xknxMock = Mock()
    xknxMock.telegrams = AsyncMock()
    KNXExposeSensor(hass, xknxMock, "binary", e_id, None, "0", "1/1/8")
    assert xknxMock.devices.add.call_count == 1, "Expected one device add"

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


async def test_expose_attribute(hass):
    """Test that an expose sends only telegrams on attribute change."""
    e_id = "fake.entity"
    a_id = "fakeAttribute"
    xknxMock = Mock()
    xknxMock.telegrams = AsyncMock()
    KNXExposeSensor(hass, xknxMock, "percentU8", e_id, a_id, None, "1/1/8")
    assert xknxMock.devices.add.call_count == 1, "Expected one device add"

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
