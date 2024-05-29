"""Tests for Shelly button platform."""

from unittest.mock import Mock

from aioshelly.const import MODEL_I3
import pytest
from pytest_unordered import unordered

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    DOMAIN as EVENT_DOMAIN,
    EventDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, inject_rpc_device_event, register_entity

DEVICE_BLOCK_ID = 4


async def test_rpc_button(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device event."""
    await init_integration(hass, 2)
    entity_id = "event.test_name_input_0"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["btn_down", "btn_up", "double_push", "long_push", "single_push", "triple_push"]
    )
    assert state.attributes.get(ATTR_EVENT_TYPE) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == EventDeviceClass.BUTTON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:0"

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "single_push",
                    "id": 0,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_EVENT_TYPE) == "single_push"


async def test_rpc_event_removal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC event entity is removed due to removal_condition."""
    entity_id = register_entity(hass, EVENT_DOMAIN, "test_name_input_0", "input:0")

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setitem(mock_rpc_device.config, "input:0", {"id": 0, "type": "switch"})
    await init_integration(hass, 2)

    assert entity_registry.async_get(entity_id) is None


async def test_block_event(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
) -> None:
    """Test block device event."""
    await init_integration(hass, 1)
    entity_id = "event.test_name_channel_1"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(["single", "long"])
    assert state.attributes.get(ATTR_EVENT_TYPE) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == EventDeviceClass.BUTTON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-relay_0-1"

    monkeypatch.setattr(
        mock_block_device.blocks[DEVICE_BLOCK_ID],
        "sensor_ids",
        {"inputEvent": "L", "inputEventCnt": 0},
    )
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "inputEvent", "L")
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_EVENT_TYPE) == "long"


async def test_block_event_shix3_1(
    hass: HomeAssistant, mock_block_device: Mock
) -> None:
    """Test block device event for SHIX3-1."""
    await init_integration(hass, 1, model=MODEL_I3)
    entity_id = "event.test_name_channel_1"

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["double", "long", "long_single", "single", "single_long", "triple"]
    )
