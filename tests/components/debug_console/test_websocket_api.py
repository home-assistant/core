"""Tests for the Debug console websocket API."""

from typing import Any

import pytest

from homeassistant.components.websocket_api import ERR_UNAUTHORIZED

from . import COMMANDS

from tests.common import MockUser
from tests.typing import MockHAClientWebSocket


@pytest.mark.parametrize("command", COMMANDS)
async def test_requires_admin(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    command: dict[str, Any],
) -> None:
    """Test the console is only available to administrators."""
    hass_admin_user.groups = []

    await websocket_client.send_json_auto_id(command)

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_UNAUTHORIZED
