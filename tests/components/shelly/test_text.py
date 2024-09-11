"""Tests for Shelly text platform."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_PLATFORM,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, register_device, register_entity


@pytest.mark.parametrize(
    ("name", "entity_id"),
    [
        ("Virtual text", "text.test_name_virtual_text"),
        (None, "text.test_name_text_203"),
    ],
)
async def test_rpc_device_virtual_text(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
) -> None:
    """Test a virtual text for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["text:203"] = {
        "name": name,
        "meta": {"ui": {"view": "field"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["text:203"] = {"value": "lorem ipsum"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "lorem ipsum"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-text:203-text"

    monkeypatch.setitem(mock_rpc_device.status["text:203"], "value", "dolor sit amet")
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "dolor sit amet"

    monkeypatch.setitem(mock_rpc_device.status["text:203"], "value", "sed do eiusmod")
    await hass.services.async_call(
        TEXT_PLATFORM,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: "sed do eiusmod"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == "sed do eiusmod"


async def test_rpc_remove_virtual_text_when_mode_label(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual text will be removed if the mode has been changed to a label."""
    config = deepcopy(mock_rpc_device.config)
    config["text:200"] = {"name": None, "meta": {"ui": {"view": "label"}}}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["text:200"] = {"value": "lorem ipsum"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        TEXT_PLATFORM,
        "test_name_text_200",
        "text:200-text",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_virtual_text_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual text will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        TEXT_PLATFORM,
        "test_name_text_200",
        "text:200-text",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry
