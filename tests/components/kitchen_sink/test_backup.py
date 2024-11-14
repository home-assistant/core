"""Test the Kitchen Sink backup platform."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def backup_only() -> AsyncGenerator[None]:
    """Enable only the backup platform.

    The backup platform is not an entity platform.
    """
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant) -> None:
    """Set up Kitchen Sink integration."""
    assert await async_setup_component(hass, "backup", {"backup": {}})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agents info."""
    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "agents": [{"id": "kitchen_sink.syncer"}],
        "syncing": False,
    }


async def test_agents_list_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test backup agents list backups."""
    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/list_backups"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == [
        {
            "agent_id": "kitchen_sink.syncer",
            "date": "1970-01-01T00:00:00Z",
            "id": "def456",
            "slug": "abc123",
            "size": 1234,
            "name": "Kitchen sink syncer",
        }
    ]
