"""Tests for Shelly select platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_PLATFORM,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import init_integration, register_device, register_entity


@pytest.mark.parametrize(
    ("name", "entity_id", "value", "expected_state"),
    [
        ("Virtual enum", "select.test_name_virtual_enum", "option 1", "Title 1"),
        (None, "select.test_name_enum_203", None, STATE_UNKNOWN),
    ],
)
async def test_rpc_device_virtual_enum(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
    value: str | None,
    expected_state: str,
) -> None:
    """Test a virtual enum for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["enum:203"] = {
        "name": name,
        "options": ["option 1", "option 2", "option 3"],
        "meta": {
            "ui": {
                "view": "dropdown",
                "titles": {"option 1": "Title 1", "option 2": None},
            }
        },
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["enum:203"] = {"value": value}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    assert (state := hass.states.get(entity_id))
    assert state.state == expected_state
    assert state.attributes.get(ATTR_OPTIONS) == [
        "Title 1",
        "option 2",
        "option 3",
    ]

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-enum:203-enum"

    monkeypatch.setitem(mock_rpc_device.status["enum:203"], "value", "option 2")
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == "option 2"

    monkeypatch.setitem(mock_rpc_device.status["enum:203"], "value", "option 1")
    await hass.services.async_call(
        SELECT_PLATFORM,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Title 1"},
        blocking=True,
    )
    # 'Title 1' corresponds to 'option 1'
    mock_rpc_device.enum_set.assert_called_once_with(203, "option 1")
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == "Title 1"


async def test_rpc_remove_virtual_enum_when_mode_label(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual enum will be removed if the mode has been changed to a label."""
    config = deepcopy(mock_rpc_device.config)
    config["enum:200"] = {
        "name": None,
        "options": ["one", "two"],
        "meta": {
            "ui": {"view": "label", "titles": {"one": "Title 1", "two": "Title 2"}}
        },
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["enum:200"] = {"value": "one"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SELECT_PLATFORM,
        "test_name_enum_200",
        "enum:200-enum",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None


async def test_rpc_remove_virtual_enum_when_orphaned(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual enum will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SELECT_PLATFORM,
        "test_name_enum_200",
        "enum:200-enum",
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
            "Device communication error occurred while calling action for select.test_name_enum_203 of Test name",
        ),
        (
            RpcCallError(999),
            "RPC call error occurred while calling action for select.test_name_enum_203 of Test name",
        ),
    ],
)
async def test_select_set_exc(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    error: str,
) -> None:
    """Test select setting with exception."""
    config = deepcopy(mock_rpc_device.config)
    config["enum:203"] = {
        "name": None,
        "options": ["option 1", "option 2", "option 3"],
        "meta": {
            "ui": {
                "view": "dropdown",
                "titles": {"option 1": "Title 1", "option 2": None},
            }
        },
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["enum:203"] = {"value": "option 1"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    mock_rpc_device.enum_set.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            SELECT_PLATFORM,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: f"{SELECT_PLATFORM}.test_name_enum_203",
                ATTR_OPTION: "option 2",
            },
            blocking=True,
        )


async def test_select_set_reauth_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test select setting with authentication error."""
    config = deepcopy(mock_rpc_device.config)
    config["enum:203"] = {
        "name": None,
        "options": ["option 1", "option 2", "option 3"],
        "meta": {
            "ui": {
                "view": "dropdown",
                "titles": {"option 1": "Title 1", "option 2": None},
            }
        },
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["enum:203"] = {"value": "option 1"}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    entry = await init_integration(hass, 3)

    mock_rpc_device.enum_set.side_effect = InvalidAuthError

    await hass.services.async_call(
        SELECT_PLATFORM,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: f"{SELECT_PLATFORM}.test_name_enum_203",
            ATTR_OPTION: "option 2",
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
