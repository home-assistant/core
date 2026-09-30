"""Tests for HTML5 Websocket API."""

from homeassistant.components.html5.websocket_api import WS_TYPE_APPKEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_CONF_PUB_KEY

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_websocket_appkey(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test websocket appkey command."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": WS_TYPE_APPKEY})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == MOCK_CONF_PUB_KEY
