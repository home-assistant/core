"""Tests for the known infrared commands."""

from typing import Any

from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.infrared import DATA_COMMANDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import captured_code, captured_code_again, seed_commands

from tests.typing import WebSocketGenerator

POWER_COMMAND = NECCommand(address=0x04FB, command=0xF7)
POWER_CODE = captured_code(POWER_COMMAND)
VOLUME_UP_CODE = captured_code(NECCommand(address=0x04FB, command=0xF6))


@pytest.mark.usefixtures("init_infrared")
async def test_create_list_update_delete(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the full lifecycle of a command over the websocket API."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "infrared/commands/list"})
    assert (await client.receive_json())["result"] == []

    await client.send_json_auto_id(
        {"type": "infrared/commands/create", "name": "Volume up", "code": POWER_CODE}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "id": "volume_up",
        "name": "Volume up",
        "code": POWER_CODE,
    }

    await client.send_json_auto_id(
        {
            "type": "infrared/commands/update",
            "command_id": "volume_up",
            "name": "Power",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"id": "volume_up", "name": "Power", "code": POWER_CODE}

    await client.send_json_auto_id({"type": "infrared/commands/list"})
    assert (await client.receive_json())["result"] == [
        {"id": "volume_up", "name": "Power", "code": POWER_CODE}
    ]

    await client.send_json_auto_id(
        {"type": "infrared/commands/delete", "command_id": "volume_up"}
    )
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id({"type": "infrared/commands/list"})
    assert (await client.receive_json())["result"] == []


@pytest.mark.usefixtures("init_infrared")
async def test_create_suggests_id_from_name(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the id of a command is suggested by its name."""
    client = await hass_ws_client(hass)

    for code in (POWER_CODE, VOLUME_UP_CODE):
        await client.send_json_auto_id(
            {"type": "infrared/commands/create", "name": "Volume up!", "code": code}
        )
        assert (await client.receive_json())["success"]

    await client.send_json_auto_id({"type": "infrared/commands/list"})
    msg = await client.receive_json()
    assert [command["id"] for command in msg["result"]] == [
        "volume_up",
        "volume_up_2",
    ]


@pytest.mark.parametrize(
    ("name", "code", "expected_error"),
    [
        pytest.param("Power", "not pronto", "Invalid infrared code", id="invalid_code"),
        pytest.param(
            "", POWER_CODE, "length of value must be at least 1", id="no_name"
        ),
    ],
)
@pytest.mark.usefixtures("init_infrared")
async def test_create_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    name: str,
    code: str,
    expected_error: str,
) -> None:
    """Test creating a command that is not valid."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "infrared/commands/create", "name": name, "code": code}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    assert expected_error in msg["error"]["message"]


@pytest.mark.usefixtures("init_infrared")
async def test_create_rejects_known_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a command that is already known is rejected."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "infrared/commands/create", "name": "Power", "code": POWER_CODE}
    )
    assert (await client.receive_json())["success"]

    second_press = captured_code_again(POWER_COMMAND)
    assert second_press != POWER_CODE

    await client.send_json_auto_id(
        {
            "type": "infrared/commands/create",
            "name": "Power again",
            "code": second_press,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    assert "same infrared command as 'Power'" in msg["error"]["message"]


@pytest.mark.usefixtures("init_infrared")
async def test_update_unknown_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test renaming a command that does not exist."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "infrared/commands/update", "command_id": "power", "name": "Power"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


@pytest.mark.usefixtures("init_infrared")
async def test_delete_unknown_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test deleting a command that does not exist."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "infrared/commands/delete", "command_id": "power"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


@pytest.mark.usefixtures("init_infrared")
async def test_create_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test recording a command requires admin access."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id(
        {"type": "infrared/commands/create", "name": "Power", "code": POWER_CODE}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


@pytest.mark.usefixtures("init_infrared")
async def test_subscribe(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a subscriber gets the commands and every change to them."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "infrared/commands/create", "name": "Power", "code": POWER_CODE}
    )
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id({"type": "infrared/commands/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"] == [
        {
            "change_type": "added",
            "command_id": "power",
            "item": {"id": "power", "name": "Power", "code": POWER_CODE},
        }
    ]

    await client.send_json_auto_id(
        {"type": "infrared/commands/delete", "command_id": "power"}
    )
    assert (await client.receive_json())["event"] == [
        {
            "change_type": "removed",
            "command_id": "power",
            "item": {"id": "power", "name": "Power", "code": POWER_CODE},
        }
    ]
    assert (await client.receive_json())["success"]


async def test_stored_commands_are_loaded(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test the commands are read back from storage."""
    seed_commands(hass_storage, [{"id": "power", "name": "Power", "code": POWER_CODE}])
    assert await async_setup_component(hass, DOMAIN, {})

    commands = hass.data[DATA_COMMANDS]
    assert commands.items() == [{"id": "power", "name": "Power", "code": POWER_CODE}]
