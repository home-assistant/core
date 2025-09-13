"""Tests for refoss_rpc binary sensor platform."""

from unittest.mock import Mock

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import mutate_rpc_device_status, register_entity, set_integration


async def test_rpc_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_overheating"
    await set_integration(hass)

    assert hass.states.get(entity_id).state == STATE_OFF

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "sys", "errors", ["overtemp"]
    )
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sys-overtemp"


async def test_rpc_binary_sensor_removal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor is removed due to removal_condition."""
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_input_1_input", "input:1-input"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setattr(mock_rpc_device, "status", {"input:1": {"state": False}})
    await set_integration(hass)

    assert entity_registry.async_get(entity_id) is None
