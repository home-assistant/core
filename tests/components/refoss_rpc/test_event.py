"""Tests for refoss_rpc button platform."""

from unittest.mock import Mock

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

from . import inject_rpc_device_event, register_entity, set_integration


async def test_rpc_button(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device event."""
    await set_integration(hass)
    entity_id = "event.test_input"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_EVENT_TYPES) == unordered(
        [
            "button_down",
            "button_up",
            "button_double_push",
            "button_long_push",
            "button_single_push",
            "button_triple_push",
        ]
    )
    assert state.attributes.get(ATTR_EVENT_TYPE) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == EventDeviceClass.BUTTON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-input:1"

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "button_single_push",
                    "id": 1,
                }
            ],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_EVENT_TYPE) == "button_single_push"


async def test_rpc_event_removal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test event entity is removed due to removal_condition."""
    entity_id = register_entity(hass, EVENT_DOMAIN, "test_input_1", "input:1")

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setitem(mock_rpc_device.config, "input:1", {"id": 1, "type": "switch"})
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"sta_1": {"enable": False}, "sta_2": {"enable": False}},
    )
    await set_integration(hass)

    assert entity_registry.async_get(entity_id) is None
