"""Tests for Shelly valve platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_GAS
import pytest

from homeassistant.components.shelly.const import (
    MODEL_FRANKEVER_WATER_VALVE,
    MODEL_NEO_WATER_VALVE,
)
from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    ValveState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
)
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


async def test_rpc_water_valve(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device Shelly Water Valve."""
    config = deepcopy(mock_rpc_device.config)
    config["number:200"] = {
        "name": "Position",
        "min": 0,
        "max": 100,
        "meta": {"ui": {"step": 10, "view": "slider", "unit": "%"}},
        "role": "position",
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["number:200"] = {"value": 0}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3, model=MODEL_FRANKEVER_WATER_VALVE)
    entity_id = "valve.test_name"

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-number:200-water_valve"

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSED

    # Open valve
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.number_set.assert_called_once_with(200, 100)

    status["number:200"] = {"value": 100}
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.OPEN

    # Close valve
    mock_rpc_device.number_set.reset_mock()
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.number_set.assert_called_once_with(200, 0)

    status["number:200"] = {"value": 0}
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSED

    # Set valve position to 50%
    mock_rpc_device.number_set.reset_mock()
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 50},
        blocking=True,
    )

    mock_rpc_device.number_set.assert_called_once_with(200, 50)

    status["number:200"] = {"value": 50}
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.OPEN
    assert state.attributes.get(ATTR_CURRENT_POSITION) == 50


async def test_rpc_neo_water_valve(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device Shelly NEO Water Valve."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:200"] = {
        "name": "State",
        "meta": {"ui": {"view": "toggle"}},
        "role": "state",
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:200"] = {"value": False}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3, model=MODEL_NEO_WATER_VALVE)
    entity_id = "valve.test_name"

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-boolean:200-neo_water_valve"

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSED

    # Open valve
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.call_rpc.assert_called_once_with(
        "Boolean.Set", {"id": 200, "value": True}
    )

    status["boolean:200"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.OPEN

    # Close valve
    mock_rpc_device.call_rpc.reset_mock()
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_rpc_device.call_rpc.assert_called_once_with(
        "Boolean.Set", {"id": 200, "value": False}
    )

    status["boolean:200"] = {"value": False}
    monkeypatch.setattr(mock_rpc_device, "status", status)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == ValveState.CLOSED
