"""Tests for Shelly cover platform."""
from unittest.mock import Mock

import pytest

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
from homeassistant.core import HomeAssistant

from . import init_integration, mutate_rpc_device_status

ROLLER_BLOCK_ID = 1


async def test_block_device_services(
    hass: HomeAssistant, mock_block_device, monkeypatch, entity_registry
) -> None:
    """Test block device cover services."""
    entity_id = "cover.test_name"
    monkeypatch.setitem(mock_block_device.settings, "mode", "roller")
    await init_integration(hass, 1)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_CLOSING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_CLOSED

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-roller_0"


async def test_block_device_update(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device update."""
    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "rollerPos", 0)
    await init_integration(hass, 1)

    assert hass.states.get("cover.test_name").state == STATE_CLOSED

    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "rollerPos", 100)
    mock_block_device.mock_update()
    assert hass.states.get("cover.test_name").state == STATE_OPEN


async def test_block_device_no_roller_blocks(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device without roller blocks."""
    monkeypatch.setattr(mock_block_device.blocks[ROLLER_BLOCK_ID], "type", None)
    await init_integration(hass, 1)
    assert hass.states.get("cover.test_name") is None


async def test_rpc_device_services(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry,
) -> None:
    """Test RPC device cover services."""
    entity_id = "cover.test_cover_0"
    await init_integration(hass, 2)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "state", "opening"
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_OPENING

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "state", "closing"
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_CLOSING

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "closed")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_CLOSED

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-cover:0"


async def test_rpc_device_no_cover_keys(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device without cover keys."""
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    await init_integration(hass, 2)
    assert hass.states.get("cover.test_cover_0") is None


async def test_rpc_device_update(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device update."""
    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "closed")
    await init_integration(hass, 2)
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSED

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "state", "open")
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover_0").state == STATE_OPEN


async def test_rpc_device_no_position_control(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device with no position control."""
    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "pos_control", False
    )
    await init_integration(hass, 2)
    assert hass.states.get("cover.test_cover_0").state == STATE_OPEN
