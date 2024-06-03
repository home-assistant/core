"""Tests for Ecovacs services."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from deebot_client.device import Device
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.vacuum import SERVICE_SEND_CUSTOM_COMMAND
from homeassistant.components.vacuum import ATTR_COMMAND, ATTR_PARAMS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def mock_device_execute_response(
    command: str, params: dict[str, Any] | list[Any]
) -> Generator[AsyncMock, None, None]:
    """Mock the device execute function response."""
    with patch.object(
        Device,
        "execute_command",
        return_value={
            "ret": "ok",
            "resp": {
                "header": {
                    "pri": 1,
                    "tzm": 480,
                    "ts": "1717113600000",
                    "ver": "0.0.1",
                    "fwVer": "1.2.0",
                    "hwVer": "0.1.0",
                },
                "body": {
                    "code": 0,
                    "msg": "ok",
                    "data": {"command": command, "params": params},
                },
            },
            "id": "xRV3",
            "payloadType": "j",
        },
    ) as mock_device_execute_response:
        yield mock_device_execute_response


@pytest.mark.usefixtures("mock_device_execute_response")
@pytest.mark.parametrize(
    ("command", "params"),
    [
        ("test_command_list", ["param1", "param2"]),
        ("test_command_dict", {"key1": "value1", "key2": "value2"}),
        ("test_command_none", None),
    ],
)
@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_send_custom_command_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_id: str,
    command: str,
    params: dict[str, Any] | list[Any] | None,
) -> None:
    """Test that send_custom_command service response snapshots match."""
    vacuum = hass.states.get(entity_id)
    assert vacuum

    assert snapshot(
        name=f"{entity_id}:custom-command-response"
    ) == await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_CUSTOM_COMMAND,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_COMMAND: command,
            ATTR_PARAMS: params,
        },
        blocking=True,
        return_response=True,
    )
