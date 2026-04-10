"""Tests for ESPHome websocket API."""

from homeassistant.components.esphome.const import CONF_NOISE_PSK
from homeassistant.components.esphome.websocket_api import ENTRY_ID, TYPE

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_get_encryption_key(
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get encryption key."""
    mock_config_entry = init_integration

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_encryption_key",
            ENTRY_ID: mock_config_entry.entry_id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "encryption_key": mock_config_entry.data.get(CONF_NOISE_PSK)
    }
