"""Tests for the Debug console integration setup."""

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_setup(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    """Test the console is set up from YAML, asking for the warning first."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "debug_console/info"})
    msg = await client.receive_json()

    assert msg["result"] == {"warning_required": True}
