"""Tests for Shelly valve platform."""

from unittest.mock import Mock

from aioshelly.const import MODEL_GAS
import pytest

from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN, ValveState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_VALVE, SERVICE_OPEN_VALVE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration

GAS_VALVE_BLOCK_ID = 6


async def test_block_device_gas_valve(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device Shelly Gas with Valve addon."""
    await init_integration(hass, 1, MODEL_GAS)
    entity_id = "valve.test_name_valve"

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-valve_0-valve"

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSED

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.OPENING

    monkeypatch.setattr(mock_block_device.blocks[GAS_VALVE_BLOCK_ID], "valve", "opened")
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.OPEN

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSING

    monkeypatch.setattr(mock_block_device.blocks[GAS_VALVE_BLOCK_ID], "valve", "closed")
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSED
