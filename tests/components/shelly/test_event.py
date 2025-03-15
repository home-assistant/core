"""Tests for Shelly button platform."""

from unittest.mock import Mock

from aioshelly.ble.const import BLE_SCRIPT_NAME
from aioshelly.const import MODEL_I3
import pytest
from pytest_unordered import unordered
from syrupy import SnapshotAssertion

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

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["btn_down", "btn_up", "double_push", "long_push", "single_push", "triple_push"]
    )
    assert state.attributes.get(ATTR_EVENT_TYPE) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == EventDeviceClass.BUTTON

    assert (entry := entity_registry.async_get(entity_id))
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

    assert (state := hass.states.get(entity_id))
    assert state.attributes.get(ATTR_EVENT_TYPE) == "single_push"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_script_1_event(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test script event."""
    await init_integration(hass, 2)
    entity_id = "event.test_name_test_script_js"

    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}-state")

    assert entity_registry.async_get(entity_id) == snapshot(name=f"{entity_id}-entry")

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "id": 1,
                    "event": "script_start",
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.attributes.get(ATTR_EVENT_TYPE) == "script_start"

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "id": 1,
                    "event": "unknown_event",
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.attributes.get(ATTR_EVENT_TYPE) != "unknown_event"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_script_2_event(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that scripts without any emitEvent will not get an event entity."""
    await init_integration(hass, 2)
    entity_id = "event.test_name_test_script_2_js"

    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}-state")

    assert entity_registry.async_get(entity_id) == snapshot(name=f"{entity_id}-entry")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_script_ble_event(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the ble script will not get an event entity."""
    await init_integration(hass, 2)
    entity_id = f"event.test_name_{BLE_SCRIPT_NAME}"

    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}-state")

    assert entity_registry.async_get(entity_id) == snapshot(name=f"{entity_id}-entry")


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

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(["single", "long"])
    assert state.attributes.get(ATTR_EVENT_TYPE) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == EventDeviceClass.BUTTON

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-relay_0-1"

    monkeypatch.setattr(
        mock_block_device.blocks[DEVICE_BLOCK_ID],
        "sensor_ids",
        {"inputEvent": "L", "inputEventCnt": 0},
    )
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "inputEvent", "L")
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.attributes.get(ATTR_EVENT_TYPE) == "long"


async def test_block_event_shix3_1(
    hass: HomeAssistant, mock_block_device: Mock
) -> None:
    """Test block device event for SHIX3-1."""
    await init_integration(hass, 1, model=MODEL_I3)
    entity_id = "event.test_name_channel_1"

    assert (state := hass.states.get(entity_id))
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        ["double", "long", "long_single", "single", "single_long", "triple"]
    )
