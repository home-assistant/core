"""Tests for the Debug console integration setup."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.components.websocket_api import ERR_UNKNOWN_COMMAND
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import SESSION_ID

from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("development_version", "config", "enabled"),
    [
        pytest.param(True, {}, True, id="development"),
        pytest.param(
            True, {DOMAIN: {"enabled": False}}, False, id="development_disabled"
        ),
        pytest.param(False, {}, False, id="release"),
        pytest.param(False, {DOMAIN: {}}, True, id="release_enabled"),
        pytest.param(False, {DOMAIN: {"enabled": False}}, False, id="release_disabled"),
    ],
)
async def test_enabled(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    development_version: bool,
    config: dict[str, Any],
    enabled: bool,
) -> None:
    """Test the console is on for development versions, and else needs YAML."""
    with patch(
        "homeassistant.components.debug_console.IS_DEVELOPMENT_VERSION",
        development_version,
    ):
        assert await async_setup_component(hass, DOMAIN, config)

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "debug_console/info"})
    msg = await client.receive_json()
    assert msg["result"] == {"enabled": enabled, "warning_required": False}

    # The commands to use it only exist while it is enabled.
    await client.send_json_auto_id(
        {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"}
    )
    msg = await client.receive_json()
    assert msg["success"] is enabled
    if not enabled:
        assert msg["error"]["code"] == ERR_UNKNOWN_COMMAND
