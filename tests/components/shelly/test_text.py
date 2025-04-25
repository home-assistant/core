"""Tests for Shelly text platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_PLATFORM,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    assert (state := hass.states.get(entity_id))
    assert state.state == "lorem ipsum"

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-text:203-text"

    monkeypatch.setitem(mock_rpc_device.status["text:203"], "value", "dolor sit amet")
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == "dolor sit amet"

    monkeypatch.setitem(mock_rpc_device.status["text:203"], "value", "sed do eiusmod")
    await hass.services.async_call(
        TEXT_PLATFORM,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: "sed do eiusmod"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    mock_rpc_device.text_set.assert_called_once_with(203, "sed do eiusmod")

    assert (state := hass.states.get(entity_id))
    assert state.state == "sed do eiusmod"


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

    assert entity_registry.async_get(entity_id) is None


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

    assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while calling action for text.test_name_text_203 of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action for text.test_name_text_203 of Test name",
        ),
    ],
)
async def test_text_set_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    error: str,
) -> None:
    """Test text setting with exception."""
    config = deepcopy(mock_rpc_device.config)
    config["text:203"] = {
        "name": None,
        "meta": {"ui": {"view": "field"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["text:203"] = {"value": "lorem ipsum"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    mock_rpc_device.text_set.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            TEXT_PLATFORM,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: f"{TEXT_PLATFORM}.test_name_text_203",
                ATTR_VALUE: "new value",
            },
            blocking=True,
        )


async def test_text_set_reauth_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test text setting with authentication error."""
    config = deepcopy(mock_rpc_device.config)
    config["text:203"] = {
        "name": None,
        "meta": {"ui": {"view": "field"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["text:203"] = {"value": "lorem ipsum"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    entry = await init_integration(hass, 3)

    mock_rpc_device.text_set.side_effect = InvalidAuthError

    await hass.services.async_call(
        TEXT_PLATFORM,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: f"{TEXT_PLATFORM}.test_name_text_203",
            ATTR_VALUE: "new value",
        },
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
