"""Tests for Shelly cover platform."""
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.const import ATTR_ENTITY_ID

from . import init_integration

ROLLER_BLOCK_ID = 1


async def test_block_device_services(hass, mock_block_device, monkeypatch):
    """Test block device cover services."""
    monkeypatch.setitem(mock_block_device.settings, "mode", "roller")
    await init_integration(hass, 1)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_name", ATTR_POSITION: 50},
        blocking=True,
    )
    state = hass.states.get("cover.test_name")
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_name"},
        blocking=True,
    )
    assert hass.states.get("cover.test_name").state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_name"},
        blocking=True,
    )
    assert hass.states.get("cover.test_name").state == STATE_CLOSING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_name"},
        blocking=True,
    )
    assert hass.states.get("cover.test_name").state == STATE_CLOSED


async def test_block_device_update(hass, mock_block_device, monkeypatch):
    """Test block device update."""
    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "rollerPos", 0)
    await init_integration(hass, 1)

    assert hass.states.get("cover.test_name").state == STATE_CLOSED

    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "rollerPos", 100)
    mock_block_device.mock_update()
    assert hass.states.get("cover.test_name").state == STATE_OPEN


async def test_block_device_no_roller_blocks(hass, mock_block_device, monkeypatch):
    """Test block device without roller blocks."""
    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "type", None)
    await init_integration(hass, 1)
    assert hass.states.get("cover.test_name") is None


async def test_rpc_device_services(hass, mock_rpc_device, monkeypatch):
    """Test RPC device cover services."""
    await init_integration(hass, 2)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_cover_0", ATTR_POSITION: 50},
        blocking=True,
    )
    state = hass.states.get("cover.test_cover_0")
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    monkeypatch.setitem(mock_rpc_device.status["cover:0"], "state", "opening")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover_0"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover_0").state == STATE_OPENING

    monkeypatch.setitem(mock_rpc_device.status["cover:0"], "state", "closing")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover_0"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSING

    monkeypatch.setitem(mock_rpc_device.status["cover:0"], "state", "closed")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover_0"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSED


async def test_rpc_device_no_cover_keys(hass, mock_rpc_device, monkeypatch):
    """Test RPC device without cover keys."""
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    await init_integration(hass, 2)
    assert hass.states.get("cover.test_cover_0") is None


async def test_rpc_device_update(hass, mock_rpc_device, monkeypatch):
    """Test RPC device update."""
    monkeypatch.setitem(mock_rpc_device.status["cover:0"], "state", "closed")
    await init_integration(hass, 2)
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSED

    monkeypatch.setitem(mock_rpc_device.status["cover:0"], "state", "open")
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover_0").state == STATE_OPEN


async def test_rpc_device_no_position_control(hass, mock_rpc_device, monkeypatch):
    """Test RPC device with no position control."""
    monkeypatch.setitem(mock_rpc_device.status["cover:0"], "pos_control", False)
    await init_integration(hass, 2)
    assert hass.states.get("cover.test_cover_0").state == STATE_OPEN
