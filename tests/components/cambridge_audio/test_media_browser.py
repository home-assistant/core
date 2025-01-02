"""Tests for the Cambridge Audio media browser."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import ENTITY_ID

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_browse_media_root(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the root browse page."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot


async def test_browse_presets(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the presets browse page."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "presets",
            "media_content_id": "",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["children"] == snapshot
