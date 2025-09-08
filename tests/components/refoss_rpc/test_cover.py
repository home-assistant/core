"""Tests for refoss_rpc cover platform."""

from unittest.mock import Mock

import pytest

from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import set_integration


async def test_rpc_device_set_cover(
    hass: HomeAssistant, mock_rpc_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test RPC device unique_ids."""
    await set_integration(hass)

    entry = entity_registry.async_get("cover.test_cover")
    assert entry
    assert entry.unique_id == "123456789ABC-cover:1"


async def test_rpc_device_services(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device turn on/off services."""
    await set_integration(hass)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    assert hass.states.get("cover.test_cover").state == STATE_CLOSED

    monkeypatch.setitem(mock_rpc_device.status["cover:1"], "state", "open")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover").state == STATE_OPEN


async def test_rpc_device_services_pos(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device turn on/off services."""
    await set_integration(hass)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_cover", ATTR_POSITION: 0},
        blocking=True,
    )
    assert hass.states.get("cover.test_cover").state == STATE_CLOSED

    monkeypatch.setitem(mock_rpc_device.status["cover:1"], "state", "open")
    monkeypatch.setitem(mock_rpc_device.status["cover:1"], "current_pos", 100)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_cover", ATTR_POSITION: 100},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("cover.test_cover").state == STATE_OPEN
