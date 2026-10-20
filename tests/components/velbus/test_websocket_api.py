"""Tests for the Velbus config panel websocket API."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.velbus.const import (
    CONF_ADVANCED_MODE,
    CONF_CHANNEL,
    CONF_CONFIG_ENTRY,
)
from homeassistant.components.velbus.websocket_api import _get_entry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import init_integration


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
    assert len(modules) == 2
    addresses = [module["address"] for module in modules]
    assert addresses.count(1) == 1
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


async def test_set_module_config_bool_string(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a boolean parameter written as the string false is stored as False."""
    param = _mock_config_parameter(key="enabled")
    param.kind = "bool"
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
            "key": "enabled",
            "value": "false",
        },
    )

    assert response["success"]
    param.set_value.assert_awaited_once_with(False)


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
            {CONF_CHANNEL: 2, "key": "name", "value": "x"},
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


@pytest.mark.parametrize(
    "command",
    [
        "velbus/config_panel/module/actions/set",
        "velbus/config_panel/module/actions/clear",
    ],
)
async def test_source_channel_above_eight_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    command: str,
) -> None:
    """Test source_channel matches the library 1-8 contract."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        command,
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 88,
            CONF_CHANNEL: 1,
            "source_address": 1,
            "source_channel": 9,
            "action": "on",
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


async def test_clear_channel_action_by_source(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test clearing programmed actions by source address and channel."""
    slot = _mock_action_slot(slot=2)
    mock_relay.clear_actions_for_source = AsyncMock(return_value=[slot])
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
            "source_address": 5,
            "source_channel": 2,
        },
    )

    assert response["success"]
    assert response["result"]["slots"][0]["slot"] == 2
    mock_relay.clear_actions_for_source.assert_awaited_once_with(5, source_channel=2)


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


async def test_get_entry_rejects_missing_config_entry_field(
    hass: HomeAssistant,
) -> None:
    """Test the entry lookup reports a message that omitted config_entry."""
    connection = MagicMock()

    assert _get_entry(hass, connection, {"id": 7}) is None

    connection.send_error.assert_called_once_with(
        7, "invalid_format", "Missing config_entry"
    )


async def test_unloaded_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test websocket commands fail when the config entry is not loaded."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/schema",
        {CONF_CONFIG_ENTRY: config_entry.entry_id, "type_id": 40},
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert "not loaded" in response["error"]["message"]


async def test_list_modules_device_id_missing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a module scanned after startup has no device registry id."""
    await _setup_entry(hass, config_entry, advanced_mode=True)
    orphan = MagicMock()
    orphan.get_addresses.return_value = [50]
    orphan.get_channels.return_value = {}
    orphan.get_name.return_value = "Orphan"
    orphan.get_type.return_value = 7
    orphan.get_type_name.return_value = "VMB1RY"
    orphan.get_serial.return_value = "orphan"
    controller.return_value.get_modules.return_value = {50: orphan}
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/modules",
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
    )

    assert response["success"]
    assert response["result"]["modules"] == [
        {
            "address": 50,
            "name": "Orphan",
            "type_id": 7,
            "type_name": "VMB1RY",
            "serial": "orphan",
            "device_id": None,
            "channels": {},
        }
    ]


async def test_set_module_config_module_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test config writes fail when the module address is unknown."""
    controller.return_value.get_module.return_value = None
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/config/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 42,
            CONF_CHANNEL: 1,
            "key": "name",
            "value": "Relay",
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "not_found"
    assert "Module 42 not found" in response["error"]["message"]


@pytest.mark.parametrize(
    ("kind", "value", "param_attrs", "expected"),
    [
        pytest.param("bool", True, {}, True, id="bool"),
        pytest.param(
            "number",
            "3.5",
            {"min_value": 0, "max_value": 10},
            3.5,
            id="number",
        ),
        pytest.param(
            "select",
            "summer",
            {"options": ["summer", "winter"]},
            "summer",
            id="select",
        ),
        pytest.param("text", "hi", {"max_length": 4}, "hi", id="text"),
    ],
)
async def test_set_module_config_coerces_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    kind: str,
    value: Any,
    param_attrs: dict[str, Any],
    expected: Any,
) -> None:
    """Test config values are coerced to the parameter kind before writing."""
    param = _mock_config_parameter(key="setting")
    param.kind = kind
    for attr, attr_value in param_attrs.items():
        setattr(param, attr, attr_value)
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
            "key": "setting",
            "value": value,
        },
    )

    assert response["success"]
    param.set_value.assert_awaited_once_with(expected)


@pytest.mark.parametrize(
    ("kind", "value", "param_attrs", "message"),
    [
        pytest.param("bool", "yes", {}, "Invalid boolean", id="bool"),
        pytest.param("number", "nope", {}, "Invalid number", id="number"),
        pytest.param("number", 0, {"min_value": 1}, "below minimum", id="number_min"),
        pytest.param("number", 9, {"max_value": 5}, "above maximum", id="number_max"),
        pytest.param(
            "select",
            "autumn",
            {"options": ["summer", "winter"]},
            "must be one of",
            id="select",
        ),
        pytest.param(
            "text", "toolong", {"max_length": 3}, "exceeds max length", id="text"
        ),
        pytest.param("color", "red", {}, "Unknown config kind", id="unknown_kind"),
    ],
)
async def test_set_module_config_rejects_invalid_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    kind: str,
    value: Any,
    param_attrs: dict[str, Any],
    message: str,
) -> None:
    """Test config values that do not match the parameter kind are rejected."""
    param = _mock_config_parameter(key="setting")
    param.kind = kind
    for attr, attr_value in param_attrs.items():
        setattr(param, attr, attr_value)
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
            "key": "setting",
            "value": value,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    assert message in response["error"]["message"]
    param.set_value.assert_not_awaited()


async def test_get_channel_actions_unsupported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action reads fail when the relay has no action table."""
    mock_module_subdevices.get_action_table.return_value = None
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
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
    assert response["error"]["code"] == "home_assistant_error"
    assert "does not support action-table programming" in response["error"]["message"]


async def test_set_channel_action_relay_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test programming an action fails when the module is unknown."""
    controller.return_value.get_module.return_value = None
    await _setup_entry(hass, config_entry, advanced_mode=True)
    client = await hass_ws_client(hass)

    response = await _ws_call(
        client,
        "velbus/config_panel/module/actions/set",
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_ADDRESS: 42,
            CONF_CHANNEL: 1,
            "source_address": 1,
            "action": "on",
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "not_found"


async def test_set_channel_action_write_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action programming failures from the library are returned as errors."""
    mock_relay.set_action = AsyncMock(side_effect=OSError("eeprom write failed"))
    mock_module_subdevices.get_channels.return_value = {1: mock_relay}
    await _setup_entry(hass, config_entry, advanced_mode=True)
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
    assert response["error"]["code"] == "home_assistant_error"
    assert "eeprom write failed" in response["error"]["message"]


async def test_clear_channel_action_relay_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test clearing an action fails when the channel has no action table."""
    mock_module_subdevices.get_channels.return_value = {}
    await _setup_entry(hass, config_entry, advanced_mode=True)
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
    assert response["error"]["code"] == "not_found"


async def test_clear_channel_action_write_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_module_subdevices: AsyncMock,
    mock_relay: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test action clear failures from the library are returned as errors."""
    mock_relay.clear_action = AsyncMock(side_effect=OSError("eeprom clear failed"))
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
            "slot": 1,
        },
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert "eeprom clear failed" in response["error"]["message"]
