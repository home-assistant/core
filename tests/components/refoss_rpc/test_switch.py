"""Tests for refoss_rpc switch platform."""

from unittest.mock import Mock

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import set_integration


async def test_rpc_device_set_switch(
    hass: HomeAssistant, mock_rpc_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test RPC device unique_ids."""
    await set_integration(hass)

    entry = entity_registry.async_get("switch.test_switch")
    assert entry
    assert entry.unique_id == "123456789ABC-switch:1"


async def test_rpc_device_services(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device turn on/off services."""
    await set_integration(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch"},
        blocking=True,
    )
    assert hass.states.get("switch.test_switch").state == STATE_ON

    monkeypatch.setitem(mock_rpc_device.status["switch:1"], "output", False)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("switch.test_switch").state == STATE_OFF

    monkeypatch.setitem(mock_rpc_device.status["switch:1"], "output", True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "switch.test_switch"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("switch.test_switch").state == STATE_ON
