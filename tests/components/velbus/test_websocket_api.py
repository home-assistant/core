"""Tests for the Velbus config panel websocket API."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.velbus.const import (
    CONF_ADVANCED_MODE,
    CONF_CHANNEL,
    CONF_CONFIG_ENTRY,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry, MockUser
from tests.typing import WebSocketGenerator


async def _setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    *,
    advanced_mode: bool = False,
) -> None:
    """Set up the Velbus integration with optional advanced mode."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, CONF_ADVANCED_MODE: advanced_mode},
    )
    await init_integration(hass, config_entry)


def _mock_action_slot(*, slot: int = 0) -> MagicMock:
    """Return a mock action-table slot."""
    action_slot = MagicMock()
    action_slot.to_dict.return_value = {
        "slot": slot,
        "empty": False,
        "source_address": 1,
        "source_channel": 2,
        "action_key": "on",
        "action_label": "On",
    }
    return action_slot


def _mock_config_parameter(*, key: str = "name") -> MagicMock:
    """Return a mock EEPROM config parameter."""
    param = MagicMock()
    param.key = key
    param.set_value = AsyncMock()
    return param


async def _ws_call(
    client: Any,
    msg_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Send a Velbus websocket command and return the response."""
    await client.send_json_auto_id({"type": msg_type, **payload})
    return await client.receive_json()


async def test_get_base_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test velbus/config_panel/get_base_data."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/get_base_data",
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
    )

    assert response["success"]
    assert response["result"] == {
        "config_entry_id": config_entry.entry_id,
        "advanced_mode": True,
        "title": config_entry.title,
    }


async def test_list_modules_includes_channels(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test modules list includes channel metadata for the panel selector."""
    mock_module_subdevices.get_channels.return_value = {1: mock_relay, 9: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/modules",
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
    )

    assert response["success"]
    modules = response["result"]["modules"]
    assert modules
    kitchen = next(module for module in modules if module["address"] == 88)
    assert kitchen["name"] == "Kitchen"
    assert kitchen["channels"] == {
        "1": {"name": "RelayName"},
        "9": {"name": "RelayName"},
    }
    assert kitchen["device_id"] is not None


async def test_get_module_schema(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test velbus/config_panel/module/schema."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)
    schema = {"type_id": 40, "sections": []}

    with patch(
        "homeassistant.components.velbus.websocket_api.get_module_type_schema",
        return_value=schema,
    ) as schema_mock:
        response = await _ws_call(
            client,
            "velbus/config_panel/module/schema",
            {CONF_CONFIG_ENTRY: config_entry.entry_id, "type_id": 40},
        )

    assert response["success"]
    assert response["result"] == schema
    schema_mock.assert_called_once_with(40)


async def test_get_module(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test velbus/config_panel/module/get returns live module data."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)
    module_data = {
        "address": 88,
        "name": "Kitchen",
        "type_id": 40,
        "type_name": "VMB2BLE",
        "serial": "a1b2c3d4e5f6",
        "sw_version": "2.0.0",
        "channels": {"1": {"name": "RelayName"}},
        "properties": {},
    }
    schema = {"type_id": 40, "sections": []}

    with (
        patch(
            "homeassistant.components.velbus.websocket_api.get_module_instance_data",
            new=AsyncMock(return_value=module_data),
        ),
        patch(
            "homeassistant.components.velbus.websocket_api.get_module_type_schema",
            return_value=schema,
        ),
    ):
        response = await _ws_call(
            client,
            "velbus/config_panel/module/get",
            {CONF_CONFIG_ENTRY: config_entry.entry_id, CONF_ADDRESS: 88},
        )

    assert response["success"]
    assert response["result"]["address"] == 88
    assert response["result"]["schema"] == schema
    assert response["result"]["device_id"] is not None
    mock_module_subdevices.get_type.assert_called()


async def test_get_module_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test module/get when the address is unknown."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    controller.return_value.get_module.return_value = None
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/get",
        {CONF_CONFIG_ENTRY: config_entry.entry_id, CONF_ADDRESS: 42},
    )

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_missing_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test websocket commands reject unknown config entries."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/get_base_data",
        {CONF_CONFIG_ENTRY: "missing-entry"},
    )

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_requires_admin(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test config panel websocket commands require an admin user."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    hass_admin_user.groups = []
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/get_base_data",
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
    )

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_set_module_config(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test writing a module config parameter."""
    param = _mock_config_parameter(key="name")
    mock_relay.get_config_parameters.return_value = [param]
    mock_module_subdevices.get_channels.return_value = {33: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/config/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 33,
            "key": "name",
            "value": "Temperature",
        },
    )

    assert response["success"]
    assert response["result"] == {"success": True}
    param.set_value.assert_awaited_once_with("Temperature")


async def test_set_module_config_requires_advanced_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test config writes are rejected without advanced mode."""
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=False)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/config/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
            "key": "name",
            "value": "Relay",
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["translation_key"] == "advanced_mode_required"


@pytest.mark.parametrize(
    ("payload_extra", "error_code"),
    [
        pytest.param(
            {CONF_CHANNEL: 1, "key": "missing", "value": "x"},
            "invalid_format",
            id="unknown_key",
        ),
        pytest.param(
            {CONF_CHANNEL: 99, "key": "name", "value": "x"},
            "not_found",
            id="missing_channel",
        ),
        pytest.param(
            {CONF_CHANNEL: 65, "key": "name", "value": "x"},
            "invalid_format",
            id="channel_out_of_range",
        ),
    ],
)
async def test_set_module_config_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    payload_extra: dict[str, Any],
    error_code: str,
) -> None:
    """Test config write validation and lookup failures."""
    param = _mock_config_parameter(key="name")
    mock_relay.get_config_parameters.return_value = [param]
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/config/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            **payload_extra,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == error_code


async def test_set_module_config_mutation_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test config write failures from the library are returned as errors."""
    param = _mock_config_parameter(key="name")
    param.set_value.side_effect = OSError("eeprom write failed")
    mock_relay.get_config_parameters.return_value = [param]
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/config/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
            "key": "name",
            "value": "Relay",
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert "eeprom write failed" in response["error"]["message"]


async def test_get_channel_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test reading an action table, including channels beyond 8."""
    table = MagicMock()
    table.get_actions = AsyncMock(return_value=[_mock_action_slot(slot=3)])
    mock_module_subdevices.get_action_table.return_value = table
    mock_module_subdevices.get_channels.return_value = {9: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/get",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 9,
            "refresh": True,
        },
    )

    assert response["success"]
    assert response["result"]["slots"] == [
        {
            "slot": 3,
            "empty": False,
            "source_address": 1,
            "source_channel": 2,
            "action_key": "on",
            "action_label": "On",
        }
    ]
    table.get_actions.assert_awaited_once_with(refresh=True, include_empty=True)


async def test_get_channel_actions_channel_out_of_range(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action-table channel schema rejects values above 32."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/get",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 33,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_get_channel_actions_relay_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action reads fail when the channel has no action table."""
    mock_module_subdevices.get_channels.return_value = {}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/get",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_set_channel_action(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test programming an action slot."""
    slot = _mock_action_slot(slot=1)
    mock_relay.set_action = AsyncMock(return_value=slot)
    mock_module_subdevices.get_channels.return_value = {12: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 12,
            "source_address": 1,
            "source_channel": 3,
            "action": "on",
        },
    )

    assert response["success"]
    assert response["result"]["slot"]["slot"] == 1
    mock_relay.set_action.assert_awaited_once()


async def test_set_channel_action_requires_advanced_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action writes are rejected without advanced mode."""
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=False)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
            "source_address": 1,
            "action": "on",
        },
    )

    assert not response["success"]
    assert response["error"]["translation_key"] == "advanced_mode_required"


async def test_clear_channel_action_by_slot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test clearing a programmed action by slot number."""
    slot = _mock_action_slot(slot=4)
    mock_relay.clear_action = AsyncMock(return_value=slot)
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/clear",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
            "slot": 4,
        },
    )

    assert response["success"]
    assert response["result"]["slots"][0]["slot"] == 4
    mock_relay.clear_action.assert_awaited_once_with(4)


async def test_clear_channel_action_missing_selector(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test clear requires either slot or source_address."""
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/clear",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_clear_channel_action_requires_advanced_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action clears are rejected without advanced mode."""
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=False)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/clear",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
            "slot": 1,
        },
    )

    assert not response["success"]
    assert response["error"]["translation_key"] == "advanced_mode_required"
